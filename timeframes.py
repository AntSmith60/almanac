'''
THROUGHLINE:
Kind of a simple wrapper for skyfield timescale handling.
Provides an array of timepoints to be used when performing positional calcs based on the requested date range and sample rate.
Also creates a mask for that array of timepoints for given days, or parts of days.
'''
# CONTINUUM: We use numpy to create boolean mask arrays
import numpy as np

# CONTINUUM: We use native datetime objects to construct the date range of interest as an input to the timescale linspace method
from datetime import datetime, timedelta
# CONTINUUM: We work soley in UTC
from zoneinfo import ZoneInfo

# CONTINUUM: The skyfield Loader provides the timescale object
from skyfield.api import Loader

'''
AFFORDANCE:
Provides a skyfield compatable time series based on date range and sample rate.
Creates masks for that series as needed.
'''
class TimeFrame():
    def __init__(self, observatory, date, days=7, sample_rate=600):
        self.observatory = observatory
        self.date = date
        self.days = days
        self.sample_rate = sample_rate

        self.samples_per_day = int((24 * 60 * 60) / self.sample_rate)

        self.ts = self.observatory.loader.timescale()
        self.times = self._get_time_series()

    '''
    SKILL:
    Creates a UTC datetime object to tether the timescale
    '''
    @staticmethod
    def _utc_anchor(date):
        return datetime(date.year, date.month, date.day, 12, tzinfo=ZoneInfo("UTC"))

    '''
    SKILL:
    Creates the timescale object that later allows time-batched observations to be calculated
    '''
    def _get_time_series(self):
        tether = self._utc_anchor(self.date)
        anchor = self._utc_anchor(tether + timedelta(days=self.days))
        num_samples = self.samples_per_day * self.days

        ts_tether = self.ts.utc(tether)
        ts_anchor = self.ts.utc(anchor)
        
        print(f"Observation window:{str(tether)} .. {str(anchor)} with {num_samples} samples at rate:{self.sample_rate} for:{self.days}d")
        return self.ts.linspace(ts_tether, ts_anchor, num_samples)

    '''
    SKILL:
    Provides a mask for the time  series for when we want to calculate specific positions
    '''
    def sample_window(self, day, first, n_samples):
        offset = (day * self.samples_per_day) + first
        mask = np.zeros(self.times.shape[0], dtype=bool)
        mask[offset:offset + n_samples] = True
        return mask
