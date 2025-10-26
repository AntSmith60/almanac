'''
THROUGHLINE:
This module holds the main UI for the app, and thus the shared internal app state.
It provides 2 dialogue panels.
The first establishes the bulk data for the plot exploration, i.e. the range of magnitudes to be provided and the days across which to make the observations. It determines how much data can be explored, and thus how long it takes to prepare the plot for observation.
The second provides exploratory controls that are near instantaneous in response. E.g. filtering the displayed magnitudes, selecting a day, rotating/scaling the view etc...
'''
# CONTINUUM: The plot displays day-by-day from UTC Noon, with times displayed as UTC. To be honest, local time handling would only give minor benefit at the cost of more UI and more code, so I'm just not doing it for this app!
from datetime import datetime, timedelta

from PyQt5.QtWidgets import (
    QWidget, QLabel, QVBoxLayout, QHBoxLayout,
    QCheckBox, QFrame, QSpinBox, QGroupBox, 
    QPushButton, QComboBox, QDateEdit, QDialog,
    QMessageBox
)
from PyQt5.QtCore import Qt, QDate

from base_ui import UIBuilder, ClickableLCD, DialControl, DialPairControl, LocationEntryDialog
from plotter import Plotter

'''
KNOWLEDGE:
This is where all the defaults get stored - you can edit this script if you like to make the app less annoying everytime you start it if the defaults don't work for you.
The most likely changes you might want to make here are:
- qloc: query location, your home vantage lat/lon
- qsize: default DPI and Inches settings
- rotation: what gets put at the top of the plot. Polar plots default to 0deg at the left, so a value of 90 here places North at the top (my default is 270, to place South at the top)
'''
class AppState:
    def __init__(self):
        # for the bulk data set-up, things that take a long time to recalc
        self.qloc  = (54, 0.0)
        self.date = datetime.now().date()
        self.day_range = 7
        self.sample_rate = 600
        self.mag_range = [-2.0, 6.0]
        self.starfield_range = [-2.0, 6.0]

        # for the dynamic UI, controls that we can implement fast
        self.qaz = (0, 360)     # 0 to 360, 0 to 360
        self.qalt = (0, 90)     # -90 to 90, -90 to 90
        self.qday = 0
        self.qtime = [0, 6]    # 0 to 86400 // self.sample_rate, 1 to (86400 // self.sample_rate) - self.qtime[0]
        self.qmag = self.mag_range
        self.qmag_star = self.starfield_range
        self.qsize = [280, 6.0]
        self.rotation = 270 # I want South at the top so thats +180, but polar plots also need +90 to get zero at the top..!


'''
AFFORDANCE:
Once the plot is available it is shown in its own window and the QueryControlPanel opens up; this provides the controls for exploring the plot.

Initially all the celestial objects are plotted in their positions at UTC Noon on the requested start date. 
One can step through the days (as per the number of days requested) using the *left* and *right* buttons either side of the displayed *date* at the top of the panel.
The position of the objects at different times on the selected date can be seen by adjusting the UTC *Start* in the *Times* group. This dial steps as per the requested sample rate - e.g. will have 144 steps per day for a sample rate of 600 seconds.

Also in the *Times* group there is a *spread* control. This draws transit arcs, of the length set by the dial, showing how far things will move in the selected timeframe. It only applies to the sun, moon, planets and the deep sky objects (of the Messier and NGC catalogues) - i.e. not for the constellations nor for the starfield itself. If the spread is set to zero there is no arc shown, and the name annotations are removed - so you can get a nice clear view of the sky itself.

To get the clearest view of what you're interested in, you can refine the plotted data using the *Altitude*, *Azimuth*, and *Magnitude*s dials. Each has a min and max setting, the range being defined by the range of calculations you asked for in the *BulkDataControlPanel*. To further aid clarity of the view, you can use the toggles (near the top of the panel) to turn sets of data on or off: The Planets, The Starfield, The constellations, The Messier objects and / or the NGC objects. Turn them all off if you want, but then you don't see nothing!

At the bottom of the panel there is a *rotation* dial. This defaults to placing south at the top of the plot. That's because my garden faces south, so it's easy for me to relate what I see on screen to what I see out of my window... you of course can rotate the plot to match your own viewing aspect.

Next to the *rotation* dial are a set of controls designed to help in creating image files from the plot. You can switch from a black background to a white background (saving ink if printing plot images) and also turn the grid on or off.

The *Set Viewport* button helps to size the plot to given pixel dimensions and aspect ratios, which you probably want to do before selecting *Save Visible Canvas* to create a *png file* of the current visible plot area.

Before saving the image you can click-drag the canvas to get the area of interest into the visible window. There are then 2 controls to manage the 'zoomification'... I know, kinda awkward, why not just have a single zoom??? Well, using 2 dials (*DPI* and *Inches* in the *Sizes* group) marries well with how the underlying plot engine (matplotlib) works, but more importantly means you can independently control the size of the annotating texts and the zoom factor of the plot it self. Otherwise we can find the annotations are just too big when zooming in. Both controls change the size of the plot, but *DPI* also effects the relative text size. Thing to do is to get the plot about right with the *Inches* control, then gently juggle the 2 controls in opposite directions until the plot size and text size both feel good. To be honest, it *is* a bit complex, we could do with a moore natural *text size*, *plot zoom* control pair - but in practice once you know the settings that work best for you it's rare to really need to juggle these.

Once the exploration is done with, close the control panel (with the top-right X) to return to the *BulkDataControlPanel*. This closes the plot window as well.

Oh, and once you are back at the *BulkDataControlPanel*, you can get out of the app with the *exit* button (or with the top-right X)
'''
class QueryControlPanel(QWidget):
    def __init__(self, plotter, viewers):
        super().__init__()
        self.plotter = plotter
        self.viewers =viewers

        ui_struct = {
            'dates': {},
            'sep': None,
            'toggles': {},
            'dials': {
                'left': {},
                'right': {}
            },
            'display': {
                'rotation': None,
                'image': {
                    'toggles': {}
                }
            }
        }

        self.setWindowTitle("Observables Control Panel")

        # Left button (◀)
        self.left_btn = QPushButton("◀")
        self.left_btn.setFixedWidth(40)
        self.left_btn.clicked.connect(self.decrement_qday)

        # Date label
        plot_date = self.plotter.state.date + timedelta(days=self.plotter.state.qday)
        self.date_label = QLabel(f"{plot_date.strftime('%d/%m/%Y')}")
        self.date_label.setAlignment(Qt.AlignCenter)
        self.date_label.setStyleSheet("font-size: 24px; font-weight: bold; color: black;")

        # Right button (▶)
        self.right_btn = QPushButton("▶")
        self.right_btn.setFixedWidth(40)
        self.right_btn.clicked.connect(self.increment_qday)

        # Add a horizontal separator
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        separator.setStyleSheet("margin-top: 4px; margin-bottom: 8px;")

        # Viewer toggles
        # viewer_layout = QHBoxLayout()
        for i, viewer in enumerate(self.viewers):
            viewer_num = i + 1
            if viewer.is_starfield:
                checkbox = QCheckBox('Constellations')
                checkbox.setChecked(viewer.constellations_on_display)
                checkbox.stateChanged.connect(lambda state, viewer_num=-(i + 1): self.toggle_viewer(viewer_num, state))
                # viewer_layout.addWidget(checkbox)
                ui_struct['toggles'][len(viewers)] = checkbox
            checkbox = QCheckBox(viewer.category)
            checkbox.setChecked(viewer.on_display)
            checkbox.stateChanged.connect(lambda state, viewer_num=i+1: self.toggle_viewer(viewer_num, state))
            ui_struct['toggles'][i] = checkbox
            # viewer_layout.addWidget(checkbox)

        alt_min_control = DialControl('min', 0, 90, plotter.state.qalt[0], True)
        alt_max_control = DialControl('max', 0, 90, plotter.state.qalt[1], True)
        altitude_control = DialPairControl("Altitude", alt_min_control, alt_max_control, on_change_callback=self.update_alt)

        az_min_control = DialControl('min', 0, 360, plotter.state.qaz[0], True)
        az_max_control = DialControl('max', 0, 360, plotter.state.qaz[1], True)
        azimuth_control = DialPairControl("Azimuth", az_min_control, az_max_control, on_change_callback=self.update_az)

        scale_factor = 0.1
        num_dial_steps = int(abs(self.plotter.state.starfield_range[1] - self.plotter.state.starfield_range[0]) / scale_factor)
        display_offset = self.plotter.state.starfield_range[0]
        star_mag_min_control = DialControl('min', 0, num_dial_steps,              0, False, scale_factor, display_offset, 'float', 5)
        star_mag_max_control = DialControl('max', 0, num_dial_steps, num_dial_steps, False, scale_factor, display_offset, 'float', 5)
        star_mag_control = DialPairControl("Starfield Magnitude", star_mag_min_control, star_mag_max_control, on_change_callback=self.update_star_mag)

        num_dial_steps = int(abs(self.plotter.state.mag_range[1] - self.plotter.state.mag_range[0]) / scale_factor)
        display_offset = self.plotter.state.mag_range[0]
        mag_min_control = DialControl('min', 0, num_dial_steps,              0, False, scale_factor, display_offset, 'float', 5)
        mag_max_control = DialControl('max', 0, num_dial_steps, num_dial_steps, False, scale_factor, display_offset, 'float', 5)
        mag_control = DialPairControl("Magnitude", mag_min_control, mag_max_control, on_change_callback=self.update_mag)

        num_dial_steps = (86400 // plotter.state.sample_rate) - 1
        scale_factor = 24 / (num_dial_steps + 1)
        start_time_control = DialControl('Start (UTC)', 0, num_dial_steps, plotter.state.qtime[0], False, scale_factor, 12.0, 't.m', 5)
        spread_control     = DialControl('Spread', 0, num_dial_steps, plotter.state.qtime[1], False, scale_factor,  0.0, 'h.m', 5)
        time_control = DialPairControl("Times", start_time_control, spread_control, on_change_callback=self.update_time)

        scale_factor = 18
        num_dial_steps = 60 # upto dpi 1080
        dpi_control = DialControl('DPI', 1, num_dial_steps, 16, False, scale_factor, 0, 'int', 4)

        scale_factor = 0.2
        num_dial_steps = 120 # upto 24"
        inch_control = DialControl('Inches', 5, num_dial_steps, 30, False, scale_factor, 0, 'float', 5)

        size_control = DialPairControl("Sizes", dpi_control, inch_control, on_change_callback=self.update_size)

        rotation_control = DialControl("Rotation", 0, 360, int(self.plotter.state.rotation), True, 1.0, -90, 'deg', on_change_callback=self.update_rotation)

        # Facecolor toggle
        self.facecolor_checkbox = QCheckBox("White")
        self.facecolor_checkbox.setChecked(self.plotter.is_white_bg)
        self.facecolor_checkbox.stateChanged.connect(self.toggle_bg)

        self.grid_checkbox = QCheckBox("Grid")
        self.grid_checkbox.setChecked(self.plotter.grid_on_state)
        self.grid_checkbox.stateChanged.connect(self.toggle_grid)

        set_viewport_button = QPushButton("Set Viewport")
        set_viewport_button.setFixedWidth(200)
        set_viewport_button.clicked.connect(self.viewport_size)

        save_button = QPushButton("Save Visible Canvas")
        save_button.setFixedWidth(200)
        save_button.clicked.connect(self.plotter.save_canvas)

        ui_struct['dates']['left']  = self.left_btn
        ui_struct['dates']['date']  = self.date_label
        ui_struct['dates']['right'] = self.right_btn
        ui_struct['sep'] = separator
        # checkbox toggles were added to the UI struct as we made them, above
        ui_struct['dials']['left']['alt']  = altitude_control
        ui_struct['dials']['right']['az']  = azimuth_control
        ui_struct['dials']['left']['star'] = star_mag_control
        ui_struct['dials']['right']['mag'] = mag_control
        ui_struct['dials']['left']['time'] = time_control
        ui_struct['dials']['right']['spread'] = size_control
        ui_struct['display']['rotation'] = rotation_control
        ui_struct['display']['image']['toggles']['bg'] = self.facecolor_checkbox
        ui_struct['display']['image']['toggles']['grid'] = self.grid_checkbox
        ui_struct['display']['image']['res']  = set_viewport_button
        ui_struct['display']['image']['save'] = save_button
        layout = QVBoxLayout()
        UIBuilder().build_ui(ui_struct, layout)
        self.setLayout(layout)

        self.plotter.plot()

    def viewport_size(self, state):
        self.plotter.window.set_viewport()

    def toggle_viewer(self, viewer_num, state):
        idx = abs(viewer_num) - 1 
        if viewer_num < 0:
            self.viewers[idx].constellations_on_display = bool(state)
        else:
            self.viewers[idx].on_display = bool(state)
        self.plotter.plot()

    def toggle_bg(self, state):
        self.plotter.set_facecolour(bool(state))
        self.plotter.set_gridcolour(bool(state), redraw=True)

    def toggle_grid(self, state):
        self.plotter.set_grid_state(bool(state))

    def update_alt(self, dial_values, scaled_values):
        self.plotter.state.qalt = scaled_values
        self.plotter.plot()

    def update_az(self, dial_values, scaled_values):
        self.plotter.state.qaz = scaled_values
        self.plotter.plot()

    def update_time(self, dial_values, scaled_values):
        self.plotter.state.qtime = dial_values
        self.plotter.plot()

    def update_star_mag(self, dial_values, scaled_values):
        self.plotter.state.qmag_star = scaled_values
        self.plotter.plot()

    def update_mag(self, dial_values, scaled_values):
        self.plotter.state.qmag = scaled_values
        self.plotter.plot()

    def update_size(self, dial_values, scaled_values):
        self.plotter.state.qsize = (int(scaled_values[0]), scaled_values[1])
        self.plotter.set_new_size()

    def update_rotation(self, dial_value, scaled_value):
        self.plotter.state.rotation = int(dial_value)
        self.plotter.set_rotation()

    def increment_qday(self):
        if self.plotter.state.qday < self.plotter.state.day_range + 1:
            self.plotter.state.qday += 1
            self.update_date_display()

    def decrement_qday(self):
        if self.plotter.state.qday > 0:
            self.plotter.state.qday -= 1
            self.update_date_display()

    def update_date_display(self):
        plot_date = self.plotter.state.date + timedelta(days=self.plotter.state.qday)
        self.date_label.setText(plot_date.strftime('%d/%m/%Y'))

        # Grey out buttons at bounds
        self.left_btn.setEnabled(self.plotter.state.qday > 0)
        self.right_btn.setEnabled(self.plotter.state.qday < self.plotter.state.day_range - 1)
        self.plotter.plot()

'''
AFFORDANCE:
When the app starts it first presents the BulkDataControlPanel.
This is where the available data for the plot is limited to the range of interest, based on the power of the machine in-use (processor cores and RAM available), what exactly you want to explore, and the patience of the astronomer - i.e. how long you are prepared to wait for the plot! Which can be several seconds to a minute or more.

The things to be provided are:
- Location, the earth-bound vantage point of the astronomer, as a lat/lon pair
- The date of interest, between 1900 and 2050
- The number of days to be calculated (more days requires more RAM)
- The sample rate (seconds) for the calculations. 
- The range of magnitudes to be plotted, both for the deep sky objects and for the overall starfield.

The code is using starfiled's *de421.bsp* ephemeris data file (stored in the *catalogues* sub-directory). *de440s.bsp* is also included in that directory so you can switch to the bigger dataset (1550 to 2650) if you like - you'll need to change the literal file references (2 of) in *observations.py* and *observe.py* to do so.

The celestial positions can be stepped, initially, from noon on the given date by the sample rate. More samples (a lower sample rate) requires more memory (but not much more processing time); so one can see how far things move in a given time-step. This is especially useful to astrophotographers who can therefore determine how long a given object will remain in-frame for a given positioning of the optic.

The catalogues typically contain magnitudes from -1.46 down to 18, but calculating every entry takes time. So the data made available to the plot can be restricted at this point.

The BulkDataControlPanel also allows the *credits* to be reviewed - so you can see where I got all the data from.

Once the limits of the processing has been set, the *load* button performs the calculations. A progress view shows what is being ccalculated, how much of it there is and how long the calculations took. If its all just too slow, you can use more conservative settings next time! The progress view has to be manually closed, so you have chance to see the processing stats. Once closed, the plot it self is revealed.
'''
class BulkDataControlPanel(QDialog):
    def __init__(self, state: AppState):
        super().__init__()
        self.state = state
        self.result = None  # Will be set to True (Load) or False (Exit)

        self.setWindowTitle("Bulk Data Setup")

        layout = QVBoxLayout()

        # Location display (static for now)
        loc_button = QPushButton("Set Location")
        loc_button.clicked.connect(self._open_location_dialog)
        layout.addWidget(loc_button)

        # Date picker
        date_label = QLabel("Date:")
        self.date_picker = QDateEdit()
        self.date_picker.setDate(QDate(self.state.date.year, self.state.date.month, self.state.date.day))
        self.date_picker.setCalendarPopup(True)
        layout.addWidget(date_label)
        layout.addWidget(self.date_picker)

        # Day range entry
        self.day_range_entry = QSpinBox()
        self.day_range_entry.setRange(1, 365)
        self.day_range_entry.setValue(self.state.day_range)

        # Sample rate dial
        self.sample_dial = DialControl("Sample Rate (s)", 1, 60, 10, False, 60.0, 0.0, 'int', 4)

        # Magnitude range
        scale_factor = 0.1
        num_dial_steps = int((18.0 - (-2.0)) / scale_factor)
        display_offset = -2.0

        self.mag_min_control = DialControl('min', 0, num_dial_steps, int((self.state.mag_range[0] - display_offset) / scale_factor), False, scale_factor, display_offset, 'float', 5)
        self.mag_max_control = DialControl('max', 0, num_dial_steps, int((self.state.mag_range[1] - display_offset) / scale_factor), False, scale_factor, display_offset, 'float', 5)
        mag_control = DialPairControl("Magnitude Range", self.mag_min_control, self.mag_max_control, on_change_callback=None)

        self.star_min_control = DialControl('min', 0, num_dial_steps, int((self.state.starfield_range[0] - display_offset) / scale_factor), False, scale_factor, display_offset, 'float', 5)
        self.star_max_control = DialControl('max', 0, num_dial_steps, int((self.state.starfield_range[1] - display_offset) / scale_factor), False, scale_factor, display_offset, 'float', 5)
        star_control = DialPairControl("Starfield Range", self.star_min_control, self.star_max_control, on_change_callback=None)


        # GROUPS
        memory_group = QGroupBox("MEMORY HUNGRY")
        memory_layout = QVBoxLayout()
        memory_group.setLayout(memory_layout)

        process_group = QGroupBox("PROCESS HEAVY")
        process_layout = QVBoxLayout()
        process_group.setLayout(process_layout)

        area_style = """
            QGroupBox {
                background-color: white;
                border: 1px solid red;
                border-radius: 5px;
                margin-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top center;
                padding: 3px;
                font-weight: bold;
                color: red;
            }
        """
        inner_style = """
            QGroupBox {
                border: 1px solid gray;
            }
            QGroupBox::title {
                subcontrol-position: top center;
                font-weight: normal;
                color: black;
            }
        """
        memory_group.setStyleSheet(area_style)
        process_group.setStyleSheet(area_style)
        star_control.setStyleSheet(inner_style)
        mag_control.setStyleSheet(inner_style)

        # Memory Hungry
        memory_layout.addWidget(QLabel("Day Range:"))
        memory_layout.addWidget(self.day_range_entry)
        memory_layout.addWidget(self.sample_dial)

        # Process Heavy
        process_layout.addWidget(mag_control)
        process_layout.addWidget(star_control)

        layout.addWidget(memory_group)
        layout.addWidget(process_group)

        # Buttons
        button_layout = QHBoxLayout()
        load_button = QPushButton("Load")
        credits_button = QPushButton("Credits")
        exit_button = QPushButton("Exit")
        button_layout.addWidget(load_button)
        button_layout.addWidget(credits_button)
        button_layout.addWidget(exit_button)
        layout.addLayout(button_layout)

        load_button.clicked.connect(self.on_load)
        credits_button.clicked.connect(self._show_credits_popup)
        exit_button.clicked.connect(self.on_exit)

        self.setLayout(layout)
        self.show()

    def on_load(self):
        # Update state from controls
        self.state.date = self.date_picker.date().toPyDate()
        self.state.day_range = int(self.day_range_entry.value())
        self.state.sample_rate = int(self.sample_dial.get_scaled_value())

        min_mag = self.mag_min_control.get_scaled_value()
        max_mag = self.mag_max_control.get_scaled_value()
        self.state.mag_range = [min_mag, max_mag]

        min_mag = self.star_min_control.get_scaled_value()
        max_mag = self.star_max_control.get_scaled_value()
        self.state.starfield_range = [min_mag, max_mag]

        self.result = True
        self.close()

    def _open_location_dialog(self):
        dialog = LocationEntryDialog(*self.state.qloc)
        if dialog.exec_() == QDialog.Accepted:
            self.state.qloc = dialog.get_location()

    def on_exit(self):
        self.result = False
        self.close()

    def closeEvent(self, event):
        if self.result is None:
            self.result = False
        super().closeEvent(event)

    def exec_and_return(self):
        self.result = None
        self.exec_()
        return self.result

    def _show_credits_popup(self):
        credits = """
        <html>
        <head>
            <style>
                body { font-family: 'Segoe UI', sans-serif; font-size: 10pt; }
                h2 { margin-bottom: 8px; }
                p { margin: 4px 0; }
                ul { margin: 4px 0 8px 20px; }
                li { margin-bottom: 4px; }
            </style>
        </head>
        <body>
            <h2>Celestial Almanac</h2>
            <p><strong>Author:</strong> Ant Smith, 2025</p>

            <h3>Data Sources</h3>
            <ul>
                <li><strong>Messier Catalogue:</strong> <a href="https://www.datastro.eu/explore/dataset/catalogue-de-messier">datastro.eu</a></li>
                <li><strong>VizieR Catalogues:</strong><br>
                    This research has made use of the VizieR catalogue access tool, CDS, Strasbourg, France.<br>
                    DOI: <a href="https://doi.org/10.26093/cds/vizier">10.26093/cds/vizier</a><br>
                    Original publication: A&amp;AS 143, 23 (2000)
                </li>
                <li><strong>Constellation Stick Figures:</strong><br>
                    © 2005–2023, Marc van der Sluys, <a href="https://hemel.waarnemen.com">hemel.waarnemen.com</a>
                </li>
                <li><strong>SKYFIELD Python Modules and API</strong></li>
            </ul>
        </body>
        </html>
        """
        msg = QMessageBox(self)
        msg.setWindowTitle("Data Source Credits")
        msg.setTextFormat(Qt.RichText)
        msg.setText(credits)
        msg.setStandardButtons(QMessageBox.Ok)
        msg.exec_()
