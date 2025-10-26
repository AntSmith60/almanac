'''
THROUGHLINE:
This module offers a collection of support classes that refine PyQt to our specific needs.
These classes either regularise the UI behaviour, or else just make PyQt easier to work with.
'''
# CONTINUUM: The app is tightly bound to PyQt for the UI.
from PyQt5.QtWidgets import (
    QWidget, QLabel, QDial, QVBoxLayout, QHBoxLayout,
    QLCDNumber, QGroupBox, QSizePolicy, QDoubleSpinBox,
    QDialog, QPushButton
)
from PyQt5.QtCore import Qt, pyqtSignal

'''
MECHANISM:
Although PyQt presents rather nicely, I find juggling the layouts damned awkward. Layouts give rise to a lot of fragile code that just intereferes with the details when we create UI objects.
So as a simplification I create UI layouts such that each container flips the orientation of its parent - i.e. vertical blocks live inside horizontal blocks that live inside vertical blocks, etc...
Once the usercode has created all of its fundamental widgets, it arranges them in a recursive dict, which is then used to direct the actual horizontal and vertical layouts.
E.g. 
        ui_struct['dates']['left']  = self.left_btn
        ui_struct['dates']['date']  = self.date_label
        ui_struct['dates']['right'] = self.right_btn
        ui_struct['dials']['left']['alt']  = altitude_control
        ui_struct['dials']['right']['az']  = azimuth_control
Creates 2 vertical groups: dates and dials. The dates group contains 3 horizontal widgets (left, date, right). The dials group contains 2 horizontal widgets (alt and az)
'''
class UIBuilder:
    @staticmethod
    def build_ui(struct, parent_layout, depth=0):
        """Recursively generates layouts and UI elements."""
        layout_class = QVBoxLayout if depth % 2 == 0 else QHBoxLayout  # Flip layout orientation
        container_widget = QWidget()
        container_layout = layout_class(container_widget)
        container_layout.setSpacing(10)
        container_layout.setContentsMargins(0, 0, 0, 0)

        if depth == 0:
            container_layout.setSpacing(20)
            container_layout.setContentsMargins(10, 10, 10, 10)

        container_layout.setAlignment(Qt.AlignLeft)
        container_widget.setLayout(container_layout)
        # container_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)

        for key, value in struct.items():
            if isinstance(value, dict):
                UIBuilder.build_ui(value, container_layout, depth + 1)
            else:
                container_layout.addWidget(value, stretch=1)
                container_widget.adjustSize()  # Ensure it resizes properly

        parent_layout.addWidget(container_widget)

'''
MECHANISM:
Wraps the QLCDNumber widget so that mouse events can by caught and signalled. Let's us reset a control when its associated number display is double clicked
'''
class ClickableLCD(QLCDNumber):
    doubleClicked = pyqtSignal()

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()

'''
MECHANISM:
Adds a numerical display to a dial control.
Therefore also manages how a dial control's range maps to application concepts (so that the displayed value makes sense to the application and user).
Dials are inherently integer based, but the values we are setting may be integers, floats, or sexagesimals (hours and minutes).
Conversion from dial integers to meaningful values is provided via the scale and offset parameters.
Our dial also allows for an on_change callback, which effectively decouples the dial from the application object it affects. Note this is only used / needed for singular dials, when we have an uber-control (e.g. a dial pair) it provides the callback.
'''
class DialControl(QWidget):
    def __init__(
        self,
        label,
        min_val,
        max_val,
        ini_val,
        wrapped = False,
        scale_factor = 1.0,
        display_offset = 0.0,
        display_format = 'int',
        display_width = 3,
        on_change_callback = None
    ):
        super().__init__()

        self.initial_value = ini_val
        self.scale_factor   = scale_factor
        self.display_offset = display_offset
        self.display_format = display_format
        self.on_change_callback = on_change_callback

        self.dial = QDial()
        self.dial.setRange(min_val, max_val)
        self.dial.setWrapping(wrapped)
        self.dial.setNotchesVisible(True)
        self.dial.setSingleStep(1)
        self.dial.setValue(self.initial_value)

        self.display = ClickableLCD()
        self.display.doubleClicked.connect(self._reset_dial)
        self.display.setSegmentStyle(ClickableLCD.Flat)
        self.display.setDigitCount(display_width)
        self.display.setStyleSheet("background-color: black; color: lime;")
        self.display.display(self.display_value())
        self.dial.valueChanged.connect(self._update)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(QLabel(label))
        layout.addWidget(self.dial)
        layout.addWidget(self.display)
        self.setLayout(layout)

    '''
    BEHAVIOUR:
    Links the dial value to the numeric display's double-click event
    '''
    def _reset_dial(self):
        self.set_value(self.initial_value)
        self._update()

        '''
    BEHAVIOUR:
    Links the dial value to the numeric display value. Also invokes any callback, linking the dial value to the app state
    '''
    def _update(self):
        self.display.display(self.display_value())
        if self.on_change_callback:
            self.on_change_callback(self.get_value(), self.get_scaled_value())

    # MECHANISM: retrieves the raw (integer) value of the dial
    def get_value(self):
        return self.dial.value()

    # MECHANISM: sets the raw (integer) value of the dial
    def set_value(self, value):
        return self.dial.setValue(value)

    # MECHANISM: displays the scaled dial value
    def display_value(self):
        disp = (self.dial.value() * self.scale_factor) + self.display_offset
        if self.display_format == 'int':
            return f"{int(disp)}"
        elif self.display_format == 'deg':
            return f"{int(disp) % 360}"
        elif self.display_format in ('t.m', 'h.m'):
            hours = int(disp) % 24
            minutes = int(round((disp - int(disp)) * 60)) % 60
            return f"{hours:02d}:{minutes:02d}"
        else:
            return f"{disp:.2f}"

    # MECHANISM: retrieves the scaled dial value
    def get_scaled_value(self):
        return (self.dial.value() * self.scale_factor) + self.display_offset


'''
MECHANISM:
Presents a pair of (related) dials (e.g. define min/max of an app concept)
Provides for an on_change callback that gets invoked when either dial of the pair is changed.
'''
class DialPairControl(QGroupBox):
    def __init__(self, name, control1, control2, on_change_callback):
        super().__init__(name)
        self.on_change_callback = on_change_callback

        if on_change_callback:
            control1.dial.valueChanged.connect(self._update)
            control2.dial.valueChanged.connect(self._update)

        # Layout
        layout = QHBoxLayout()
        layout.addWidget(control1)
        layout.addWidget(control2)

        self.setLayout(layout)
        self.controls = (control1, control2)

    def _update(self):
        scaled_values = []
        dial_values = []
        for control in self.controls:
            scaled_values.append(control.get_scaled_value())
            dial_values.append(int(control.get_value()))
        self.on_change_callback(dial_values, scaled_values)

'''
AFFORDANCE:
Provides a dialogue that allows the lat/long of the observation vantage point to be provided.
Would be sweet to update this to a map picker, but that's madly complex!
Allows the GDPR sensitive "this is where I am" information to be encapsulated and hidden from the general UI view
'''
class LocationEntryDialog(QDialog):
    def __init__(self, lat, lon):
        super().__init__()
        self.setWindowTitle("Set Location")
        self.setModal(True)

        self.lat_entry = QDoubleSpinBox()
        self.lat_entry.setRange(-90.0, 90.0)
        self.lat_entry.setDecimals(6)
        self.lat_entry.setValue(lat)

        self.lon_entry = QDoubleSpinBox()
        self.lon_entry.setRange(-180.0, 180.0)
        self.lon_entry.setDecimals(6)
        self.lon_entry.setValue(lon)

        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Latitude:"))
        layout.addWidget(self.lat_entry)
        layout.addWidget(QLabel("Longitude:"))
        layout.addWidget(self.lon_entry)

        button_layout = QHBoxLayout()
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)

        self.setLayout(layout)

    def get_location(self):
        return self.lat_entry.value(), self.lon_entry.value()
