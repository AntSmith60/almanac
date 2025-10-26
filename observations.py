'''
THROUGHLINE:
This module resolves the full (fixed) set of catalogues and provides the mechanism for performing the positional calculations for every plotted sky object.
It IS readilly extensible and flexible, but I didn't build a UI for selecting catalogues, so will need editing to change source data (#sorrynotsorry)
'''
# CONTINUUM: Catalogue proccessing can take time (we have thousands of sky objects) so we will report the processing time on a per catalogue basis
import time
# CONTINUUM: We use numpy just to create small colour arrays
import numpy as np
# CONTINUUM: Source data is in CSVs, so we process with Pandas
import pandas as pd

# CONTINUUM: We use the skyfield api to perform the time-batched positional calcs fromm a given vantage
from skyfield.api import (
    Loader,
    wgs84
)
# CONTINUUM: We did use hipparcos to draw the starfield, but the constellations data references V50 (Harvard References) which does not directly correlate to the hipparccos data set - so we now draw the starfield using V50; but I have kept hipparcos as a reference of how we used to live...
from skyfield.data import hipparcos

from catalogue import RawType, Catalogue
from observe import Observe

'''
AFFORDANCE:
Loads the skyfield ephemeris data (de421.bsp from the *catalogues* sub-directory) and creates the observation vantage point
'''
class Observatory:
    def __init__(self, loc):
        self.loc = (float(loc[0]), float(loc[1]))
        self.loader = Loader('./catalogues')
        self.ephemeris = self.loader('de421.bsp')
        self.vantage = wgs84.latlon(self.loc[0], self.loc[1])

        self.observer = self.ephemeris['earth'] + self.vantage

'''
AFFORDANCE:
Creates a 'viewer' for each of the disk-bound CSV catalogues.
A viewer is the full set of catalogue data (name, RA/Dec degrees, magnitudes etc..) and decor that allows the catalogued objects' positions to be calculated and plotted.
We work with a fixed set of catalogues. I could have built a UI to select the catalogues of interest, but I didn't. This is easy to extend though.
The CSV heavy lifting is done by the general purpose *catalogue* module, here we apply it to each of our provisioned catalogues.
'''
class Observables:
    # KNOWLEDGE: We declare how many catalogues we have, so the external UI can create itself before we actually resolve eveything. I don't like having to do this statically but since the whole module statically defines the catalogue set it is not wholly inapparopriate!
    num_viewers = 4

    def __init__(self, observatory, times, state):
        self.observatory = observatory
        self.times = times
        self.state = state

        start = time.perf_counter()
        self.planets = self.catalogue_planets()
        # self.hipparcos = self.catalogue_hipparcos()
        self.v50 = self.catalogue_v50()
        self.messier = self.catalogue_messier()
        self.ngc2000 = self.catalogue_ngc2000()
        cat_time = time.perf_counter() - start
        print(f"CATALOGUE Processing took {cat_time}s")

        self.viewer_defs = [
            [self.planets, 'PLANET', (0.0,0.5,1.0), False],
            # [self.hipparcos, 'STAR', (1.0,1.0,1.0), False],
            [self.v50, 'STAR', (1.0,1.0,1.0), True],
            [self.messier, 'MDSO', (1.0,0.0,0.0),  False],
            [self.ngc2000, 'NDSO', (1.0,0.2,1.0), False]
        ]

    '''
    MECHANISM:
    We do not have a CSV file for the planets, sun and moon - their data comes from the ephemeris. BUT to keep things aligned downstream we deal with these in like manner to the other catalogues. I.e. we create a small dataframe that looks like it came from a catalogue CSV file.
    '''
    def catalogue_planets(self):
        print("=== EPHEMERIS CAT ===================")
        # would have been nice to have seperate inks for each of these but its just too messy visually and code-wise
        ephemeris_names = [
            "neptune barycenter",
            "uranus barycenter",
            "saturn barycenter",
            "jupiter barycenter",
            "mars",
            "venus",
            "mercury",
            "sun",
            "moon"
        ]

        planet_list = []
        for name in ephemeris_names:
            try:
                body = self.observatory.ephemeris[name]
            except KeyError:
                continue

            # Observe the body at a single time to extract RA/Dec
            astrometric = self.observatory.observer.at(self.times[0]).observe(body)
            ra, dec, distance = astrometric.radec()

            ra_deg = ra.degrees
            dec_deg = dec.degrees
            ra_hours = ra.hours

            magnitude = 1.0

            planet_list.append({
                'name': name,
                'ra_deg': ra_deg,
                'dec_deg': dec_deg,
                'magnitude': magnitude
            })

        planet_catalogue = Catalogue(
            pd.DataFrame(planet_list), 
            'name',
            'ra_deg', RawType.DEGREES, 
            'dec_deg', RawType.DEGREES, 
            'magnitude', (0.0, 1.0)
        )
        planet_catalogue.df['__target_type'] = 'ephemeris'
        planet_catalogue.df['__sizes'] = 10
        planet_catalogue.df.loc[planet_catalogue.df['__name'] == 'moon', '__sizes'] = 30
        planet_catalogue.df.loc[planet_catalogue.df['__name'] == 'sun', '__sizes'] = 60
        return planet_catalogue

    # Hipparcos was used for the star field, but now deprecated since we use V50 instead to align with the constellations data
    def catalogue_hipparcos(self):
        print("=== HIPPPARCOS CAT ===================")
        with self.observatory.loader.open(hipparcos.URL) as f:
            hipparcos_list = hipparcos.load_dataframe(f)
        # this adds the hip column:
        hipparcos_list = hipparcos_list.reset_index()

        print(f"Star data from:{hipparcos.URL}")
        print("Columns:", hipparcos_list.columns.tolist())
        print("\nFirst row:\n", hipparcos_list.iloc[0])
        hipparcos_catalogue = Catalogue(
            hipparcos_list,
            'hip',
            'ra_degrees', RawType.DEGREES,
            'dec_degrees', RawType.DEGREES,
            'magnitude', self.state.starfield_range
        )
        return hipparcos_catalogue

    '''
    MECHANISM:
    V50 is the bright star catalogue (Hoffleit & Warrenm 1991) we use it to draw the starfield and the constellations
    '''
    def catalogue_v50(self):
        print("=== V50 CAT ===================")
        v50_list = pd.read_csv('./catalogues/v50.csv', sep=',')
        print("Columns:", v50_list.columns.tolist())
        v50_catalogue = Catalogue(
            v50_list, 
            'HR',
            'RAJ2000', RawType.SEXAGESIMAL, 
            'DEJ2000', RawType.SEXAGESIMAL, 
            'Vmag', self.state.starfield_range
        )
        return v50_catalogue

    '''
    MECHANISM:
    Messier is the deep-sky object catalogue (Messier 1781) we use it to plot nebulae, clusters, and galaxies
    '''
    def catalogue_messier(self):
        print("=== MESSIER CAT ===================")
        messier_list = pd.read_csv('./catalogues/catalogue-de-messier.csv', sep=';')
        messier_catalogue = Catalogue(
            messier_list, 
            'Messier',
            'RA (Right Ascension)', RawType.SEXAGESIMAL, 
            'Dec (Declinaison)', RawType.SEXAGESIMAL, 
            'Magnitude', self.state.mag_range
        )
        return messier_catalogue

    '''
    MECHANISM:
    NGC2000 is the extended deep-sky catalogue (Sinnott 1988) we use it to plot nebulae, clusters, and galaxies beyond the Messier set
    '''
    def catalogue_ngc2000(self):
        print("=== NGC2000 CAT ===================")
        ngc_list = pd.read_csv('./catalogues/ngc2000.csv', sep=';')
        ngc2000_catalogue = Catalogue(
            ngc_list,
            'Name',
            'ra', RawType.SEXAGESIMAL, 
            'dec', RawType.SEXAGESIMAL, 
            'Magnitude', self.state.mag_range
        )
        return ngc2000_catalogue

    '''
    This is the workhorse. It executes the positional calcs versus times for every object in each catalogue. Much of the work is handed off to the observations multiprocess
    '''
    def make_viewers(self, progress):
        viewers = []
        for catalogue, category, colour, is_starfield in self.viewer_defs:
            progress_text = f"{len(catalogue.df)} {category} objects"
            long_step = len(catalogue.df) > 999
            if not progress.step(progress_text, long_step):
                return None
            viewers.append(Observe(category, colour, is_starfield))
            viewers[-1].observations(self.observatory.loc, catalogue, self.times)

        return viewers
