'''
This module is made as lightweight as possible since it is dispatched to multiple processes. It does the heavy lifting of calculating the position of every catalogue object (many thousands) at every timepoint (many hundreds).
'''
# CONTINUUM: we refer the os library just to get the cpu count so we can constrain the multiprocessing batch size
import os
# CONTINUUM: Because this is the heavy lifting we use the time library to report how long things take
import time
# CONTINUUM: as far as we can we use numpy vectorisation in all our calcs
import numpy as np
# CONTINUUM: Skyfield does a great job of vectorising our timepoint series (of hundreds of samples), but only on a per target basis. Since we have thousands of targets we use multiprocessing to batch them up
from concurrent.futures import ProcessPoolExecutor

from skyfield.api import (
# CONTINUUM: Because we are using multiprocessing this module has to be pickleable, so we cannot share the loaded ephemeris, each process has too load it for itself. Ugh. We do still benefit from the multiprocessing though...
    Loader,
    wgs84,
# CONTINUUM: We use skyfield's Star method to define observation targets. Note we are only using RA/Dec, Star can accept proper motion type data also (and some catalogues provide that) but since we are only creating a sky explorer that level of accuracy is not needed...
    Star
)

'''
MECHANSIM:
Iterates over a number of sky objects using skyfield's timeseries batched positional calcs for each. Applies in-place numpy vectorised operations to convert raw AltAz data into plotable datapoints. The iteration here is where we need to optimise to the fullest.
'''
def compute_batch(vantage_location, rows, times):
    loader = Loader('./catalogues')
    ephemeris = loader('de421.bsp')
    vantage = wgs84.latlon(vantage_location[0], vantage_location[1])
    observer = ephemeris['earth'] + vantage
    obs = observer.at(times)

    N = len(rows)
    T = len(times)  # assuming times is your Skyfield time array
    trajectories = np.empty((N, T, 2), dtype=np.float32)

    for i, row in enumerate(rows):
        if row['__target_type'] == 'ephemeris':
            target = ephemeris[row['__name']]
        else:
            target = Star(ra_hours=row['__ra_hours'], dec_degrees=row['__dec_deg'])

        altaz = obs.observe(target).apparent().altaz()
        np.subtract(90.0, altaz[0].degrees, out=trajectories[i, :, 0])
        np.mod(altaz[1].degrees, 360,       out=trajectories[i, :, 1])
        np.deg2rad(trajectories[i, :, 1],   out=trajectories[i, :, 1])

    return trajectories

'''
SKILL:
A helper method that simply yields a chunk of catalogue targets
'''
def chunk_dataframe(df, chunk_size=500):
    for i in range(0, len(df), chunk_size):
        yield df.iloc[i:i+chunk_size]

'''
SKILL:
A helper method that wraps the call to the compute method so the process mapper can dispatch the batches - we need this because pool.map expeccts a single argument for the mapped method invocation.
'''
def unpack_and_compute(arg):
    return compute_batch(*arg)

'''
AFFORDANCE:
This is the main process object that provides calculated positions of the targets.
Having done so it then provides methods for filtering (by time window) and masking (by AltAz or magnitude)
'''
class Observe:
    def __init__(self, category, ink, is_starfield):
        self.is_starfield = is_starfield
        self.on_display = True
        self.constellations_on_display = True

        self.observatory = None
        self.catalogue = None
        self.category = category
        self.ink = ink

        self.times = None
        self.trajectories = None
        self.default_size = 10
        self.sizes = None
        self.colours = None
        self.names = []
        self.magnitudes = None

        self.max_workers = max(1, os.cpu_count() // 2)
        self.pool = ProcessPoolExecutor(max_workers=self.max_workers)

    '''
    SKILL:
    Splits a catalogue of targets into chunks and dispatches the positional calculations across cores.
    Small catalogues are executed immediately in the main process.
    '''
    def observations(self, vantage_location, catalogue, times):
        start_t = time.perf_counter()

        self.catalogue = catalogue
        self.times = times

        self.names = np.array(catalogue.df['__name'])
        self.magnitudes = np.array(catalogue.df['__magnitude'])
        self.sizes = np.array(catalogue.df['__sizes'])
        self.colours = np.array(catalogue.df['__brightness'])
        if not self.is_starfield:
            self.colours[:] = [tuple(self.ink)] * len(self.colours)

        chunk_size = max(275, len(catalogue.df) // self.max_workers)
        batches = list(chunk_dataframe(catalogue.df, chunk_size=chunk_size))
        args = [
            (vantage_location, batch_df.to_dict('records'), times)
            for batch_df in batches
        ]

        init_t = time.perf_counter() - start_t

        if len(batches) == 1:
            batch_results = [unpack_and_compute(args[0])]
        else:
            batch_results = list(self.pool.map(unpack_and_compute, args))

        self.trajectories = batch_results[0]

        for batch in batch_results[1:]:
            self.trajectories = np.concatenate((self.trajectories, batch))

        bx_t = time.perf_counter() - start_t - init_t
        print(f"Observations Timing::{init_t} {bx_t}")

    '''
    SKILL:
    Filters the calculated positions by a given time range (which is a timeseries mask we got from the timeframes module) - this reduces the amount of data we then have to process when applying any other filters or transforms (rotations etc)
    '''
    def get_altaz_window_for_all(self, time_mask):
        altaz = self.trajectories[:, time_mask]
        return altaz

    '''
    SKILL:
    Creates an AltAz range limited positional mask for the time_mask filtered trajectories.
    Here we mask rather than filter since the query is discontiguous (unlike time filtering, which is always a contiguous block of sample points)
    '''
    def get_positional_mask(self, time_mask, alt_range=(0,90), az_range=(0,360)):
        deg_alt = (90 - alt_range[1], 90 - alt_range[0])
        rad_az = np.deg2rad(az_range)
        altaz = self.trajectories[:, time_mask]

        # Compute positional mask per object
        alt = altaz[:,:,0]
        az  = altaz[:,:,1]

        if rad_az[0] < rad_az[1]:
            positional_mask = (alt >= deg_alt[0]) & (alt <= deg_alt[1]) & \
                              (az >= rad_az[0]) & (az <= rad_az[1])
        else:
            positional_mask = (alt >= deg_alt[0]) & (alt <= deg_alt[1]) & \
                              ((az >= rad_az[0]) | (az <= rad_az[1]))

        return positional_mask

    '''
    SKILL:
    Creates a Magnitude range limited mask for the time_mask filtered trajectories.
    Here, again, we mask rather than filter since the query is discontiguous
    '''
    def get_magnitude_mask(self, mag_range=(-2.0,18.0)):
        return (self.magnitudes >= mag_range[0]) & (self.magnitudes <= mag_range[1])
