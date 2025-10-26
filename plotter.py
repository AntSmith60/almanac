'''
THROUGHLINE:
This module presents the plot in an independant window.
It provides methods to operate the display from the QueryControlPanel.
When it comes to plottting, the entire plot is remade for every change that is requested. Suprisingly this is quite fast enough. I *could* have created line collections etc that get updated on change (rather than recreating all plot elements every time) - but that is much more complex and as I've said, this is all actually fast enough. Unless on your PC it isn't!
'''
# CONTINUUM: for several operations we use numpy masks on the raw calculated position data. We also use allclose and deg2rad numpy vectorised operations.
import numpy as np

# CONTINUUM: we use matplotlib as our plot generator
import matplotlib
matplotlib.rcParams['toolbar'] = 'none'
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure

from screen_ui import ScrollablePlotWindow

'''
AFFORDANCE:
This class renders and presents the sky plot as controled by the QueryControlPanel.
'''
class Plotter():
    def __init__(self, state, viewers, timeframe, constellations):
        self.state = state
        self.viewers = viewers
        self.timeframe = timeframe
        self.constellations = constellations

        self.is_white_bg = False
        self.grid_on_state = False
        self.bg_colour = "black"
        self.grid_colour = "white"

        size = int(state.qsize[1])
        dpi =  int(state.qsize[0])
        self.fig = Figure(figsize=(size, size), dpi=dpi)
        canvas = FigureCanvas(self.fig)
        self.ax = self.fig.add_subplot(111, projection='polar')

        self.set_grid_state(self.grid_on_state)
        self.set_facecolour(self.is_white_bg)
        self.set_gridcolour(self.is_white_bg, redraw=True)

        self.window = ScrollablePlotWindow(self.fig)

    '''
    SKILL:
    Closes the plot window and cleans everything up.
    Called by the QueryControlPanel when it closes, the user cannot close this window directly (it's a nonsense to do so!)
    '''
    def close(self):
        # Close the Qt window
        if self.window:
            self.window.close()
            self.window.deleteLater()

        # Clear the figure and canvas
        if self.fig:
            self.fig.clf()
            plt.close(self.fig)

        # Nullify references (optional but tidy)
        self.fig = None
        self.ax = None
        self.window = None

    '''
    MECHANISM:
    Sets the size of the plot within the window - not the window itself.
    User can drag the window shape, or set the window size via the viewport size control.
    The QueryControlPanel size controls call this method to change the PLOT size
    '''
    def set_new_size(self):
        self.fig.set_dpi(self.state.qsize[0])
        self.fig.set_size_inches(self.state.qsize[1], self.state.qsize[1])

        w, h = self.fig.get_size_inches()
        dpi = self.fig.get_dpi()
        pixel_size = int(w * dpi), int(h * dpi)

        self.window.canvas.setMinimumSize(*pixel_size)
        self.window.canvas.resize(*pixel_size)
        self.window.refresh_canvas()

    '''
    MECHANISM:
    Allows the user to orientate the plot via the QueryControlPanel's rotation dial
    '''
    def set_rotation(self):
        self.ax.set_theta_offset(np.deg2rad(self.state.rotation))
        self.fig.canvas.draw_idle()

    '''
    MECHANISM:
    Sets (does not apply) the required colour of various things to maintain contrast when switching between black and white backgrounds, returning the background colour that should now be used. Doesn't affect the plot, just persists the current colour set to be used.
    '''
    def _set_colours(self, state):
        if state:
            self.is_white_bg = True
            self.bg_colour = "white"
            self.grid_colour = (0.2, 0.2, 0.2, 0.3)  # Black with 30% opacity
            return "black"
        else:
            self.is_white_bg = False
            self.bg_colour = "black"
            self.grid_colour = (0.8, 0.8, 0.8, 0.3)  # White with 30% opacity
            return "white"

    '''
    MECHANISM:
    Called by the QueryControlPanel when the background colour is toggled; Stores the required colour set (via _set_colours) and applies the plot area (not axis) colours
    '''
    def set_facecolour(self, state, redraw=False):
        fg_col = self._set_colours(state)

        # Set full figure background
        self.fig.patch.set_facecolor(self.bg_colour)

        # Set plot (axes) background
        self.ax.set_facecolor(self.bg_colour)

        current_title = self.ax.get_title()
        self.ax.set_title(current_title, color=fg_col)

        if redraw:
            self.fig.canvas.draw_idle()

    '''
    MECHANISM:
    Called by the QueryControlPanel when background colour is toggled to update the grid (if it is on view) and axis colours
    '''
    def set_gridcolour(self, state, redraw=False):
        self._set_colours(state)

        if self.grid_on_state:
            # Set grid color
            self.ax.grid(True, color=self.grid_colour)

        # set tick and spine colors for full contrast
        self.ax.tick_params(colors=self.grid_colour)
        for spine in self.ax.spines.values():
            spine.set_color(self.grid_colour)

        if redraw:
            self.fig.canvas.draw_idle()

    '''
    MECHANISM:
    Called by the QueryControlPanel when the grid is turned on or off, using the persisted colours set
    '''
    def set_grid_state(self, state):
        self.grid_on_state = state

        if self.grid_on_state:
            self.ax.grid(True, color=self.grid_colour, linewidth=0.5)
            altitudes = [0, 30, 60, 75, 90]     # Altitude labels
            self.ax.set_yticks(altitudes)
            self.ax.set_yticklabels(altitudes[::-1])  # Reverse to show 90 at centerself.fig.canvas.draw_idle()
        else:
            self.ax.grid(False)
            self.ax.set_yticks([])
            self.ax.set_yticklabels([])

        self.fig.canvas.draw_idle()

    '''
    MECHANISM:
    Draws the plot as per the current QueryControlPanel settings
    '''
    def plot(self):
        fig = self.fig
        ax = self.ax

        qaz = self.state.qaz
        if self.state.qaz[0] == self.state.qaz[1]:
            qaz = [0, 360]

        # PROSE: Completely clears the current plot and remakes from scratch
        ax.clear()

        ax.set_rlim(0, 90)
        ax.set_thetamin(0)
        ax.set_thetamax(360)
        ax.set_theta_direction(-1)
        ax.set_theta_zero_location('N')  
        self.ax.set_theta_offset(np.deg2rad(self.state.rotation))

        ax.set_title('Temporal-Spatial Observables (Polar Alt/Az)', fontsize=12, color='white')
        self.set_grid_state(self.grid_on_state)
        fig.subplots_adjust(left=0.1, right=0.9, top=0.9, bottom=0.1)

        # Iterates over each of the views
        for viewer_num, viewer in enumerate(self.viewers):
            # skips views that have been toggled off
            if viewer.is_starfield:
                if not viewer.on_display and not viewer.constellations_on_display:
                    continue
            elif not viewer.on_display:
                continue

            obj_type = viewer.category
            if viewer.trajectories.shape[0] == 0:
                continue

            # Gets a (small) chunk of the overall time series to limit the amount of data we have to work with - gets 1 sample for each target at the current time of the current day
            temporal_chunk = self.timeframe.sample_window(self.state.qday, self.state.qtime[0], 1)
            altaz = viewer.get_altaz_window_for_all(temporal_chunk)

            # Masks the data in line with the AltAz and Magnitude min/max settings
            positional_mask = viewer.get_positional_mask(temporal_chunk, alt_range=self.state.qalt, az_range=qaz)
            mag_range = self.state.qmag_star if viewer.is_starfield else self.state.qmag
            magnitude_mask = viewer.get_magnitude_mask(mag_range)
            combined_mask = positional_mask & magnitude_mask[:, np.newaxis]

            try:
                # just continue with next viewer if the UI settings have left us with no data
                alt = altaz[:,0,0][combined_mask[:,0]]
                az  = altaz[:,0,1][combined_mask[:,0]]
            except:
                continue

            sizes = viewer.sizes[combined_mask[:,0]]
            if viewer.is_starfield:
                # Draws the starfield as a scatter plot, then adds the constellation lines
                if viewer.on_display:
                    colour = viewer.colours[combined_mask[:,0]]
                    fc = np.array(self.ax.get_facecolor()[:3])
                    if np.allclose(fc, [1.0, 1.0, 1.0]):
                        colour = 1.0 - colour
                    ax.scatter(az, alt, s=sizes, color=colour, label=obj_type)

                if viewer.constellations_on_display:
                    alt = altaz[:,0,0][positional_mask[:,0]]
                    az  = altaz[:,0,1][positional_mask[:,0]]
                    names = viewer.names[positional_mask[:,0]]

                    hr_to_pos = {hr: (az[i], alt[i]) for i, hr in enumerate(names)}
                    segments_by_group, labels = self.constellations.get_visible_segments_and_labels(hr_to_pos)

                    colour = (0.3, 0.8, 0.4)
                    # Add each LineCollection
                    for segments in segments_by_group:

                        lc = LineCollection(segments, colors=colour, linewidths=0.5, alpha=0.6)
                        ax.add_collection(lc)

                    # Add labels
                    for x, y, abr in labels:
                        ax.text(x, y, abr, fontsize=8, color=colour,
                                ha='left', va='bottom', weight='bold', alpha=0.5)

            else:
                # Draws each of the catalogues as scatter plots
                colour = viewer.ink
                ax.scatter(az, alt, s=sizes, color=colour, label=obj_type)

                # Gets a wider chunk of data (based on the Spread control) to draw in the transit arcs, filtered as per the scatter plot itself
                temporal_chunk = self.timeframe.sample_window(self.state.qday, self.state.qtime[0], self.state.qtime[1])
                windowed_altaz = viewer.get_altaz_window_for_all(temporal_chunk)
                windowed_mask = viewer.get_positional_mask(temporal_chunk, alt_range=self.state.qalt, az_range=qaz)
                combined_mask = windowed_mask & magnitude_mask[:, np.newaxis]

                segments = []
                colour = viewer.ink

                # creates line collections for the transit arcs and adds target names to the plot
                for altaz, mask, name, in zip(windowed_altaz, combined_mask, viewer.names):
                    if np.any(mask):
                        arc = altaz[mask] 
                        segments.append(arc[:, [1, 0]])

                        first_visible_idx = np.argmax(mask)
                        x = altaz[first_visible_idx, 1]
                        y = altaz[first_visible_idx, 0]
                        ax.text(x, y, name, fontsize=6, color=colour, ha='center', va='bottom')

                lc = LineCollection(segments, colors=colour, linewidths=0.5, alpha=0.6)
                ax.add_collection(lc)

        # Finally, refreshes the canvas
        fig.canvas.draw_idle()
        plt.pause(0.001)

    '''
    MECHANISM:
    Called by the QueryControlPanel save visible canvas button.
    Polar plots are drawn with zero at the right, so we calculate the true plot rotation by subtracting 90 from the current rotation setting. We also retrieve the current facecolour so the save method can work out what overstamp colour to use for its North indicator.
    '''
    def save_canvas(self):
        rotation = (self.state.rotation - 90) % 360
        facecolour = np.array(self.ax.get_facecolor()[:3])
        self.window.save_visible_canvas(rotation, facecolour)

