'''
WORLD:
The almanac is a means to explore the positions of celestial objects from any given vantage point (on earth). By building the almanac I became much more familiar with the night sky above my back garden, and I hope it could be  a good familiarisation tool for others just starting out in astronomy or astrophotography. Seasoned astronomers might well sccoff at its simple premise, but for me just being able to visualise which way everything moves and how far things move in a minute or an hour, or day by day, was really helpful. Seeing when the sun and the moon transit together, or else are in opposition, is helpful for planning night sky shoots. Observing just when Orion does, or does not, rise above the bushes at the end of my garden, actually quite thrilling (I love Orion, so easy to spot when he's around).

The software operates in 2 main stages:
- Setting up the bulk data so that the sky can be drawn
- Manipulating the drawn plot to explore how things move over time

The first stage takes significant time and memory. On my 36-core workstation plotting everything down to a magnitude of 18 across a full lunar cycle takes just over 1 minute and consumes 8GB of RAM. More conservative settings, say a week's worth of data down to a magnitude of 6, takes around 10 seconds using 2GB of RAM. The second sttage, off exploring the pplot, all happens pretty fast so one can rotate, drag, zoom and filter the plotted data interactively.

Note that setting longer time ranges for the plot increases the memory required, but has little impact on the bulk data processing time (thanks to the magic of skyfield's time-vectored calculations). Requesting more observations (i.e. extending the magnitude range of the plotable objects) increases the processing cost (because skyfield does not vectorise multiple targets). That said, if you are interested in faint objects, you can limit upper range, e.g. plot only magnitudes between 6 and 18 to filter out the brightest objects. It all just depeneds on what you want to explore, and how good your PC is!

The data plotted comes from several sources (see the 'credits'). The sun moon and planetary positions are provided by skyfield. The starfield it self from Vizier's V50 catalogue. Deep sky objects are taken from the famous Messier catalogue and from the NGC 2000 catalogue; so that's quite comprehensive. The raw data is found in CSV files in the 'catalogues' sub-directory of the script's working directory. You can readily add more catalogues here, but you would need to link them in by modifying the *observations.py* script. If you do, you _should_ see the new catalogue automagically apppears in the plot, with a checckbox to turn it on and off..! Well I hope, I tried to make the thing extensible. Note that this observations script makes use of *catalogue.py* to process CSV files, which is quite flexible regards the nature of the data in the catalogue (e.g. ascensions can be in degrees, sexagesimal or hour angles) and the required column headers. It doesn't account for any kind of comment lines in a CSV file (such as one gets when downloading from Vizier) - so those need manually stripping-out...

Having gone to much trouble to make this little app, I couldn't resist also adding the constellation stick-figures. Constellations really help me navigate the night sky so seeing them was quite a boon. I used Marc van der Sluy's data for this (again, see the 'credits'), so thanks Marc. 

INSTALLATION
The app is a set of Python 3.12 scripts, you will also need to install the following packages:
    pip install numpy==2.1.3 skyfield==1.53 PyQt5==5.15.11 pandas==2.2.3 matplotlib==3.10.3 astropy==7.1.0

It might all work with later versions, but the above reflects the development environment.

Don't forget that the skyfield ephemeris files and the CSV catalogues are also required (in the sub-directoty *catalogues*)!
'''

# CONTINUUM: the standard sys library allows us to retrieve command line arguments and to exit cleanly
import sys
# CONTINUUM: the standard time library lets us provide process timings
import time

# CONTINUUM: We are built as a PyQt app, and we use the PyQt figure canvass backend with matplotlib
from PyQt5.QtWidgets import QApplication, QProgressDialog, QWidget, QLabel, QSizePolicy, QPushButton
from PyQt5.QtCore import Qt

from timeframes import TimeFrame
from observations import Observatory, Observables
from plotter import Plotter
from catalogue import Constellations
from almanac_ui import AppState, QueryControlPanel, BulkDataControlPanel

'''
MECHANISM:
We allow the progress dialogue to be closed if things are taking just too damn long
'''
class AbortableDialog(QProgressDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.was_closed = False

    def closeEvent(self, event):
        self.was_closed = True
        super().closeEvent(event)

'''
MECHANISM:
A progress dialogue that sits between the bulk data setup and the plot exploration stages.
Shows contextual text for each step of data preparation and keeps track of how long each step takes.
'''
class DawnTreader(QWidget):
    def __init__(self, ini_text, steps):
        self.ini_text = ini_text
        self.steps = steps

        self.flags = Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint| Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint

        self.dialog = None
        self.current_text = self.ini_text
        self.current_step = 0
        self.timer = None

    def start(self):
        self.aborted = False
        self.dialog = AbortableDialog(self.ini_text, None, 0, self.steps, flags=flags)

        self.dialog.setWindowModality(Qt.ApplicationModal)
        self.dialog.setWindowTitle("Please Wait...")
        self.dialog.setMinimumDuration(0)
        self.dialog.setCancelButton(None)
        self.dialog.setAutoClose(False)
        self.dialog.setAutoReset(False)

        label = self.dialog.findChild(QLabel)
        if label:
            font = label.font()
            font.setPointSize(12)
            label.setFont(font)

            label.setAlignment(Qt.AlignRight | Qt.AlignTop)  # or Right if you prefer
            label.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.MinimumExpanding)
            label.setWordWrap(True)

            layout = self.dialog.layout()
            if layout:
                layout.setSizeConstraint(QLayout.SetMinimumSize)

        self.timer = time.perf_counter()
        self.current_step = 0
        self.dialog.setLabelText(self.ini_text + "...")
        self.current_text = self.ini_text
        self.dialog.show()
        QApplication.processEvents()

    def step(self, step_text, long_step=False):
        if self.dialog.was_closed:
            return False

        self.current_step += 1
        this_timer = time.perf_counter()
        self.current_text += f" [{round(this_timer - self.timer, 3)}]s\n{step_text}"
        self.timer = this_timer
        display_text = self.current_text
        if self.current_step < self.steps - 1:
            display_text += "...\n"
        else:
            close_button = QPushButton("Close")
            close_button.clicked.connect(self.dialog.close)
            self.dialog.setCancelButton(close_button)
            self.dialog.setWindowTitle("Voyage Ready")
            # Add a clsoe button now ????
        if long_step:
            display_text += "\n-- THIS MIGHT TAKE SOME TIME --\n"
        self.dialog.setValue(self.current_step)
        self._setText(display_text)
        QApplication.processEvents()

        return True

    def _setText(self, text):
        lines = text.split('\n')
        html = '<p style="line-height:150%">'
        html += '<br>'.join(lines)
        html += '</p>'

        label = self.dialog.findChild(QLabel)
        if label:
            label.setText(html)
            label.adjustSize()
            self.dialog.adjustSize()
        else:
            self.dialog.setLabelText(text)

'''
THROUGHLINE:
The main process runs until we explicitly EXIT the BulkDataControlPanel.
We initially present the BulkDataControlPanel alllowing the user to constrain the memory and time requirements of the exploration.
When the user presses the LOAD button we step through all the data preparations, using the DawnTreader to display progress
Once the data has been prepared we launch the QueryControlPanel to allow the exploration.
When the QueryControlPanel is closed we return to the BulkDataControlPanel
'''    
if __name__ == "__main__":

    state = AppState()
    app = QApplication(sys.argv)

    flags = Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint| Qt.WindowSystemMenuHint | Qt.WindowCloseButtonHint

    progress = DawnTreader("Preparing observables", 4 + Observables.num_viewers)

    data_panel = BulkDataControlPanel(state)
    data_panel.setWindowFlags(Qt.Dialog | flags)
    while True:
        if not data_panel.exec_and_return():
            break

        progress.start()

        # PROSE: Create the skyfield ephemeris and observation vantage
        if not progress.step("Build Observatory"):
            continue
        observatory = Observatory(state.qloc)

        # Create the skyfield timescale timeseries
        if not progress.step("Build TimeFrame"):
            continue
        observation_window = TimeFrame(observatory, state.date, state.day_range, state.sample_rate)

        # Load the targets from the various catalogues, filtered by magnitude etc
        if not progress.step("Process Catalogues"):
            continue
        observables = Observables(observatory, observation_window.times, state)

        # Make the positional calculations for all targets across the timeseries
        viewers = observables.make_viewers(progress)
        if viewers is None:
            continue

        # Prepare the constellations data
        if not progress.step("Define Constellations"):
            continue
        constellations = Constellations(observables.v50.df, './catalogues/ConstellationLines.csv')

        # create the plot
        if not progress.step("Create Plot"):
            continue
        plotter = Plotter(state, viewers, observation_window, constellations)

        progress.dialog.exec_()
        progress.step("READY")

        panel = QueryControlPanel(plotter, viewers)
        panel.setWindowFlags(Qt.Dialog | flags)
        panel.setAttribute(Qt.WA_DeleteOnClose)
        panel.show() 
       
        panel.destroyed.connect(plotter.window.close)
        app.exec_()
        plotter.close()
        del plotter

    sys.exit()
