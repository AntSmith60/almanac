'''
THROUGHLINE:
This module handles astronomical data sets in CSV files from variuos places. 
It uses pandas to load CSV files then adds internal columns (prefixed by double underscore) containing normalised data.
We create one catalogue object for each CSV file source.

This module also allows us to create a catalogue of constellations. These are obviously plotted differently to real sky objects, and so is a completely different kind of catalogue.
'''
# CONTINUUM: We create an enum for the types of co-ords we might have to handle
from enum import Enum
# CONTINUUM: We use a little bit of numpy to help convert magnitudes into display brightness values
import numpy as np
# CONTINUUM: Pandas is our main processing library as we are handling CSV files
import pandas as pd

# CONTINUUM: Astropy converts various co-ord representations into degrees
from astropy.coordinates import SkyCoord
import astropy.units as u

'''
KNOWLEDGE:
The different ways in which a CSV file may present co-ord data. I.e. As DEGREES, in SEXAGESIMAL format or as HOURANGLEs
'''
class RawType(Enum):
   DEGREES = 'deg'
   SEXAGESIMAL = 'sexagesimal'
   HOURS = 'hourangle'

'''
AFFORDANCE:
Here we provide a pandas' dataframe that has (likely) been loaded from CSV file. 
We nominate the columns that contain the needful information and (where needed) the format in which that information has been provided.
We also perform a first-level taming of the data, since we are dealing with many thousands of sky objects. Rows with no magnitude value are completely droppped, and then further filtered by the range of magnitudes the user has asked for.
'''
class Catalogue:
    def __init__(self, df, name_col, raw_ra_col, raw_ra_type, raw_dec_col, raw_dec_type, mag_col, mag_range):
        self.df = df.copy()

        # PROSE: Pre-check: If we already have all the columns we work with then nothing more to do
        if self._precheck_derived_cols(['__name', '__ra_deg', '__dec_deg', '__ra_hours', '__magnitude', '__target_type', '__norm_mag', '__sizes', '__brightness']):
            return

        # Pre-check: if we are to convert co-ords, make sure we can create the intermediate columns we will need
        self._raw_type_check(raw_ra_type, [RawType.DEGREES, RawType.HOURS, RawType.SEXAGESIMAL], '__ra_str', self.df)
        self._raw_type_check(raw_dec_type, [RawType.DEGREES, RawType.SEXAGESIMAL], '__dec_str', self.df)

        # Normalize name column, using row indices as the name if there is no source name column
        if name_col == '':
            self.df['__name'] = self.df.index.astype(int)
            name_col = '__name'

        # Pre-check all provided column names exist
        self._precheck_source_cols([name_col, mag_col, raw_ra_col, raw_dec_col])

        name_col = self._rename_col(name_col, '__name')

        # Normalize magnitude column, drop blanks and filter by required range. Keep the original magnitudes but also create a norm_mag column such that min magnitudes are zero and max magnitudes are 1.0
        mag_col = self._rename_col(mag_col, '__magnitude')
        self._cleanse_nan(mag_col)
        with_magnitude_count = len(self.df)

        self.df = self.df[self.df['__magnitude'] <= mag_range[1]]
        self.df = self.df[self.df['__magnitude'] >= mag_range[0]]

        mags = self.df['__magnitude']
        normed = 1.0 - (mags - mags.min()) / (mags.max() - mags.min())
        self.df['__norm_mag'] = normed

        # Use the norm_mag values to derive columns for plot size and colour relative to magnitude
        mags = self.df['__norm_mag']
        gamma_inv = 1 / 2.2

        self.df['__sizes'] = np.maximum(0.25, mags * 4)

        brightness = np.power(np.maximum(0.2, mags), gamma_inv)
        self.df['__brightness'] = [np.array([b, b, b]) for b in brightness]

        print(f"Filtered by magnitude[{mag_range}]: {with_magnitude_count} → {len(self.df)} rows retained")

        # drop rows where other columns contain poor data
        if raw_ra_type in [RawType.DEGREES, RawType.HOURS]:
            self._cleanse_nan(raw_ra_col)
        else:
            self._cleanse_nan(raw_ra_col, numerics=False)
        if raw_dec_type == RawType.DEGREES:
            self._cleanse_nan(raw_dec_col)
        else:
            self._cleanse_nan(raw_dec_col, numerics=False)

        # If necessary split the combined RA/Dec column
        raw_ra_col, raw_dec_col = self._col_splitter(raw_ra_col, raw_dec_col)

        # Process RA/Dec from provided format to degrees
        self._process_skypos(raw_ra_col, raw_ra_type, '__ra')
        self._process_skypos(raw_dec_col, raw_dec_type, '__dec')

        # Construct SkyCoord now that both RA and Dec are known
        coords = None
        if '__ra_str' in self.df.columns and '__dec_str' in self.df.columns:
            coords = SkyCoord(ra=self.df['__ra_str'], dec=self.df['__dec_str'], unit=(u.hourangle, u.deg))
        elif '__ra_str' in self.df.columns and '__dec_deg' in self.df.columns:
            coords = SkyCoord(ra=self.df['__ra_str'], dec=self.df['__dec_deg'] * u.deg, unit=(u.hourangle, u.deg))
        elif '__ra_deg' in self.df.columns and '__dec_str' in self.df.columns:
            coords = SkyCoord(ra=self.df['__ra_deg'] * u.deg, dec=self.df['__dec_str'], unit=(u.deg, u.deg))
        elif '__ra_deg' in self.df.columns and '__dec_deg' in self.df.columns:
            coords = SkyCoord(ra=self.df['__ra_deg'] * u.deg, dec=self.df['__dec_deg'] * u.deg, unit=(u.hourangle, u.deg))
        if coords is None:
            raise ValueError("Unable to construct SkyCoord: insufficient or mismatched RA/Dec inputs.")

        self.df['__ra_deg'] = coords.ra.deg
        self.df['__dec_deg'] = coords.dec.deg
        # add a column that identiifies the source type of the catalogue
        self.df['__target_type'] = 'star'

        # Create column for RA in hours
        if '__ra_hours' not in self.df.columns and '__ra_deg' in self.df.columns:
            self.df['__ra_hours'] = self.df['__ra_deg'].astype(float) / 15.0

    '''
    MECHANISM:
    First, it is a nonsense to say that Declination is specified in HOURS, so we guard against that userccode error
    Then, if we are to convert from sexagesimal we have to ensure the intermediate column does not already exist
    '''
    @staticmethod
    def _raw_type_check(rawtype, allowed, intermediate_col, df):
        if rawtype not in allowed:
            raise ValueError(f"Unhandled format: {rawtype}")
        if rawtype == RawType.SEXAGESIMAL:
            if intermediate_col in df.columns:
                raise ValueError(f"Intermediate column {intermediate_col} already exist.")

    '''
    MECHANISM:
    Removes rows where the column contains non-numerics (if it is a numeric, not string column) and rows where the column value is empty (numeric or string)
    '''
    def _cleanse_nan(self, col, numerics=True):
        row_count = len(self.df)
        if numerics:
            self.df[col] = pd.to_numeric(self.df[col], errors='coerce')
        self.df.dropna(subset=[col], inplace=True)
        print(f"NaN Cleansed[{col}]: {row_count} → {len(self.df)}")

    '''
    MECHANISM:
    Specifically for the case where RA/Dec are provided as a string in a single column
    If we specify the same column for 2 of the needed columns (specifically RA/Dec) then we need to split the column.
    We can only do so if the required intermediate colummns do not already exist.
    If we cannot split into exactly 2 columns we raise an error.
    Otherwise we return the names of the split (intermediate) columns that we created.
    '''
    def _col_splitter(self, col1, col2):
        if col1 != col2:
            return col1, col2

        if '__raw_ra' in self.df.columns or '__raw_dec' in self.df.columns:
            raise ValueError("Intermediate columns '__raw_ra' or '__raw_dec' already exist.")

        combined = self.df[col1].astype(str)
        split_coords = combined.str.strip().str.split(r'\s+', expand=True)

        if split_coords.shape[1] != 2:
            raise ValueError("Combined RA/Dec column must contain exactly two space-separated components.")

        self.df['__raw_ra'] = split_coords[0]
        self.df['__raw_dec'] = split_coords[1]
        return '__raw_ra', '__raw_dec'

    '''
    SKILL:
    Renames a source column to our standard (internal) name, if needs be
    '''
    def _rename_col(self, src_name, std_name):
        if src_name != std_name:
            self.df.rename(columns={src_name: std_name}, inplace=True)
        return std_name

    '''
    SKILL:
    If some, but not all, of our internal working columns already exist in the CSV then we can't entirely trust the source so we raise an error.
    Otherwise we return a boolean that indicates either all of our derived columns already exist (and we can use them) or none of our derived columns already exist (so we can create them).
    '''
    def _precheck_derived_cols(self, derived_columns):
        existing = [col for col in derived_columns if col in self.df.columns]
        if 0 < len(existing) < len(derived_columns):
            raise ValueError(f"Columnular clash: partial presence of derived columns {existing}. File needs cleaning.")

        return len(existing) == len(derived_columns)

    '''
    SKILL:
    A simple check that one or more source colummns exists in the dataframe
    '''
    def _precheck_source_cols(self, source_cols):
        required_cols = []
        for col_set in source_cols:
            if isinstance(col_set, list):
                required_cols += col_set
            else:
                required_cols += [col_set]
        for col in required_cols:
            if col not in self.df.columns:
                raise ValueError(f"Missing expected column: {col}")

    '''
    MECHANISM:
    Performms the RA/Dec conversions from source type to DEGREES
    Catering for multicolumn definition when source type is SEXAGESIMAL
    '''
    def _process_skypos(self, raw_col, col_type, result_col_prefix):
        if isinstance(raw_col, list):
            if col_type != RawType.SEXAGESIMAL:
                raise ValueError("Degrees or hours should not be split across multiple columns.")

            if len(raw_col) != 3:
                raise ValueError("Sexagesimal must have exactly 3 columns: hours, minutes, seconds.")

            h, m, s = self.df[raw_col[0]], self.df[raw_col[1]], self.df[raw_col[2]]
            self.df[f'{result_col_prefix}_str'] = h.astype(str) + 'h' + m.astype(str) + 'm' + s.astype(str) + 's'

        else:
            if col_type == RawType.DEGREES:
                self.df.rename(columns={raw_col: f'{result_col_prefix}_deg'}, inplace=True)
            elif col_type == RawType.HOURS:
                self.df[f'{result_col_prefix}_deg'] = self.df[raw_col].astype(float) * 15.0
            elif col_type == RawType.SEXAGESIMAL:
                self.df.rename(columns={raw_col: f'{result_col_prefix}_str'}, inplace=True)


'''
AFFORDANCE:
This is kind of very specific but that's the nature of the source data.
We have a CSV file that identifies stars from the V50 catalogue that make up each of the (88) constellations.
We use this with the V50 catalogue to create a set of line segment definitioons for each constellation.
'''
class Constellations:
    def __init__(self, v50_df, lines_fn):
        self.v50_df = v50_df

        # PROSE: Load and clean constellation lines
        lines_df = pd.read_csv(lines_fn)
        lines_df.columns = [col.strip() for col in lines_df.columns]

        # Strip whitespace from all string columns
        for col in lines_df.select_dtypes(include='object').columns:
            lines_df[col] = lines_df[col].map(lambda x: x.strip() if isinstance(x, str) else x)

        # Forward fill constellation names for cases where we need multiple line collections to draw a constellation (i.e. pen has to come off the page to draw it)
        lines_df['abr'] = lines_df['abr'].ffill()

        # Add a sequence ID based on original row order, for when a constellation has more than 1 sequencce of points to plot (multiple lines)
        lines_df['seq_id'] = lines_df.index

        # Melt (like a pivot) so we get 1 row per star ident instead of 31 star idents per row
        star_cols = [f's{str(i).zfill(2)}' for i in range(1, 32)]
        melted = lines_df.melt(id_vars=['abr', 'seq_id'], value_vars=star_cols, var_name='seq', value_name='HR')

        # Clean Harvard Reference (HR) values, dropping rows where there is no HR star ident (i.e. we didn't need all 30 possible idents to draw this line)
        melted = melted[melted['HR'].apply(lambda x: str(x).strip().isdigit())]
        melted['HR'] = melted['HR'].astype(int)

        # Identify missing HRs
        v50_hr_set = set(self.v50_df['__name'].dropna().astype(int))
        missing_hr = sorted(set(melted['HR']) - v50_hr_set)
        if missing_hr:
            print(f"⚠️ HRs in ConstellationLines not found in V/50: {missing_hr}")

        # Final dataframe: constellation (abbreviation and line number), sequence, HR - which can later be converted to plottable lines once we have done the observations and know the positions of the referenced stars
        self.constellation_lines = melted[['abr', 'seq_id', 'seq', 'HR']]

    '''
    MECHANISM:
    Given the current positions of Harvard References create the plotable line segments using the constellation data
    '''
    def get_visible_segments_and_labels(self, hr_to_pos):
        """
        Returns:
            segments_by_group: list of segment lists (each for one line group)
            labels: list of (x, y, abr) tuples for labeling
        """
        segments_by_group = []
        labels = []

        # Track which constellations we've labeled
        labeled_constellations = set()

        # Group by constellation and lines of the constellation
        for (abr, seq_id), group in self.constellation_lines.groupby(['abr', 'seq_id']):
            group_sorted = group.sort_values('seq')
            hr_sequence = group_sorted['HR'].tolist()

            segments = []
            for i in range(len(hr_sequence) - 1):
                hr1, hr2 = hr_sequence[i], hr_sequence[i + 1]
                if hr1 in hr_to_pos and hr2 in hr_to_pos:
                    segments.append([hr_to_pos[hr1], hr_to_pos[hr2]])

            if segments:
                segments_by_group.append(segments)

            # Add label once per constellation
            if abr not in labeled_constellations:
                for hr in hr_sequence:
                    if hr in hr_to_pos:
                        # some points in the constellation might not be visible
                        x, y = hr_to_pos[hr]
                        labels.append((x, y, abr))
                        labeled_constellations.add(abr)
                        break

        return segments_by_group, labels