'''
THROUGHLINE:
This module provides all the screen based UI primitives.
It is tightly bound to the PyQT and matplotlib libraries.
It provides entry points for UI features that allow the viewport to be sized and saved.
It manages the main plot display window, adding canvas dragability and viewpoort resize behaviours
'''
# CONTINUUM: We use numpy's allclose method just to work out if we have a light or dark background
import numpy as np

# CONTINUUM: We link the matplotlib FigureCanvas to the window
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

# CONTINUUM: We use PyQt for the UI throughout this app
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QScrollArea, QWidget, QFileDialog, QDialog, 
    QLineEdit, QPushButton, QLabel, QVBoxLayout, QHBoxLayout
)
from PyQt5.QtGui import QPainter, QPen, QColor, QFont, QPolygonF, QFontMetrics, QPixmap, QTransform
from PyQt5.QtCore import QPointF
from PyQt5.QtCore import Qt

'''
MECHANISM:
When we save an image of a plot that has been refined (with the filters and scaling etc) we actually save the visible viewport not the entire plot. This is because the saved image is meant to be a reference to what we are looking at when we get to the vantage point (like when I step out of my backdoor and into my garden) and we can typically only see a section of the sky from the vantage; so we print only a section of the entire plot. Thus we can scale and crop the plot to make it more readable.

So we set the viewport size to match the print size we are aiming for. This works well on my 4K monitor which has larger pixel resolution than my A4 printer! If I had a smaller monitor or a larger printer I'd want a different mechanism, but I don't...

Setting the viewport size is a seperate action to saving the plot because, once set, we probably want to then drag the canvas a little to get the exact right portion of the sky in view.

The viewport can be set to exact x/y pixel dimensions. Or one dimension can be set to a given pixel count and then the aspect ration buttons (16:9, A series, square) can be used to set the other dimension's pixel count; just as a convenience.
'''
class ViewportResizeDialog(QDialog):
    def __init__(self, parent_window):
        super().__init__(parent_window)
        self.setWindowTitle("Set Viewport Dimensions")
        self.parent_window = parent_window

        layout = QVBoxLayout()

        # Width controls
        self.width_entry = QLineEdit()
        layout.addWidget(QLabel("Viewport Width"))
        layout.addWidget(self.width_entry)
        layout.addLayout(self._quick_buttons(self.width_entry, "width"))

        # Height controls
        self.height_entry = QLineEdit()
        layout.addWidget(QLabel("Viewport Height"))
        layout.addWidget(self.height_entry)
        layout.addLayout(self._quick_buttons(self.height_entry, "height"))

        # Apply button
        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self._apply_resize)
        layout.addWidget(apply_btn)

        self.setLayout(layout)
        self._populate_current_size()

    def _populate_current_size(self):
        pixmap = self.parent_window.scroll.viewport().grab()
        self.width_entry.setText(str(pixmap.width()))
        self.height_entry.setText(str(pixmap.height()))

    def _quick_buttons(self, target_entry, axis):
        btn_layout = QHBoxLayout()

        def set_aspect(ratio):
            other_entry = self.height_entry if axis == "width" else self.width_entry
            try:
                other_val = int(other_entry.text())
                new_val = int(other_val * ratio) if axis == "width" else int(other_val / ratio)
                target_entry.setText(str(new_val))
            except ValueError:
                pass  # Ignore if other field isn't valid

        # HD: 16:9
        hd_btn = QPushButton("16:9")
        hd_btn.clicked.connect(lambda: set_aspect(16 / 9))

        # A Series: √2
        a_btn = QPushButton("A Series")
        a_btn.clicked.connect(lambda: set_aspect(2 ** 0.5))

        # Square: 1:1
        sq_btn = QPushButton("Square")
        sq_btn.clicked.connect(lambda: set_aspect(1))

        for btn in [hd_btn, a_btn, sq_btn]:
            btn_layout.addWidget(btn)

        return btn_layout

    def get_dimensions(self):
        try:
            w = int(self.width_entry.text())
            h = int(self.height_entry.text())
            return w, h
        except ValueError:
            return None

    def _apply_resize(self):
        self.accept()


'''
MECHANISM:
Hooks mouse events so we can click-drag the canvas within the viewport by expressely setting the scrollbar values.
Damping is applied since mouse events fire furiously and the drag operation is twitchy as hell without it. The damping can mean the canvas lags behind mouse movements but that's the price we pay for a smooth operation. There's probs a better way (I know for example that Photoshop canvas dragging is way better than this!) but this is good enough; the value of this feature hardly warrants a more complex solution. I think this is a prime example of where done is way better than perfect.
'''
class DraggableCanvas(FigureCanvas):
    def __init__(self, fig):
        super().__init__(fig)
        self.setMouseTracking(True)
        self._drag_pos = None

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.pos()

    def mouseMoveEvent(self, event):
        if self._drag_pos:
            delta = event.pos() - self._drag_pos
            self._drag_pos = event.pos()
            scroll = self.parent().parent()  # QScrollArea

            damping = 0.8
            scroll.horizontalScrollBar().setValue(
                scroll.horizontalScrollBar().value() - int(delta.x() * damping)
            )
            scroll.verticalScrollBar().setValue(
                scroll.verticalScrollBar().value() - int(delta.y() * damping)
            )

    def mouseReleaseEvent(self, event):
        self._drag_pos = None


'''
AFFORDANCE:
This allows us to present the plot within a window, you know, so we can actually see it.
The canvas of the created window is set to the (provided) matplotlib's FigureCanvas (i.e the plot) using the derived draggable canvas class.
We use the (primary) screen and plot geometries to set the window size.
Here we also provide the logic that allows the window to be resized to certain dimensions (using the ViewportResizeDialogue), and to save the viewport when the (external) UI demands such.
Note, because we expect the saved plot image is typically zoomed-in and cropped we probably do not have the polar grid axis on view when the plot is saved. So the code goes to a lot of trouble to add an overstamp North indicator to the saved image.

'''
class ScrollablePlotWindow(QMainWindow):
    def __init__(self, fig):
        super().__init__()
        self.setWindowTitle("Celestial Plot Viewer")
        self.setWindowFlags(Qt.Window | Qt.CustomizeWindowHint | Qt.WindowTitleHint| Qt.WindowSystemMenuHint)

        # self.canvas = FigureCanvas(fig)
        self.canvas = DraggableCanvas(fig)

        # Get figure size in pixels
        w_inches, h_inches = fig.get_size_inches()
        dpi = fig.get_dpi()
        fig_w, fig_h = int(w_inches * dpi), int(h_inches * dpi)

        # Get available screen size
        screen_rect = QApplication.primaryScreen().availableGeometry()
        screen_w, screen_h = screen_rect.width(), screen_rect.height()

        # Choose the smaller of figure or screen size
        win_w = min(fig_w + 40, screen_w)
        win_h = min(fig_h + 40, screen_h)

        self.scroll = QScrollArea()
        self.scroll.setWidget(self.canvas)
        self.scroll.setWidgetResizable(False)

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.addWidget(self.scroll)

        self.setCentralWidget(container)
        self.show()

        # Resize window
        self.resize(win_w, win_h)

    '''
    MECHANISM:
    We wrap the window canvas draw function so that the window and the plot are both refreshed when needed.
    '''
    def refresh_canvas(self):
        self.canvas.draw()
        self.canvas.updateGeometry()

    '''
    MECHANISM:
    Public interface for setting the viewport size.
    Invokes the UI dialogue to get the requested size and then updates the viewport by calling _set_to_res
    '''
    def set_viewport(self):
        dialog = ViewportResizeDialog(self)
        if dialog.exec_():
            dims = dialog.get_dimensions()
            if dims:
                target_w, target_h = dims
                self._set_to_res(target_w, target_h)

    '''
    SKILL:
    Sets the window size so that the inner viewport matches the requested size.
    We cannot directly set the inner viewport size, so we use a 2-step approach.
    First we set the window size (which we can do) to the requested viewport size.
    Then we get the resulting viewport dimensions - which will be smaller than we want because of scrollbars and such.
    This allows us to infer how much bigger the window size needs to be in order to achieve the requested viewport size.
    So then finally we set the window size to the inferred size...
    ...sort of messy, but way simpler than trying to calculate the sizes of all the window furniture!
    '''
    def _set_to_res(self, target_width=1920, target_height=1080):
        self.resize(target_width, target_height)

        viewport = self.scroll.viewport()
        pixmap = viewport.grab()  # Grabs only what's visible

        current_w = pixmap.width()
        current_h = pixmap.height()

        delta_w = target_width - current_w
        delta_h = target_height - current_h

        self.resize(self.width() + delta_w, self.height() + delta_h)
        
        return

    '''
    MECHANISM:
    Allows the external UI to call on the logic that saves the visible canvas.
    - Gets the pixel map of the viewport (visible canvas)
    - Overstamps the North indicator
    - Prompts for filename/path
    '''
    def save_visible_canvas(self, rotation, facecolour):
        # Get the visible region of the scroll area
        viewport = self.scroll.viewport()
        pixmap = viewport.grab()  # Grabs only what's visible

        self._stamp_north_arrow(pixmap, rotation, facecolour)
        filename, _ = QFileDialog.getSaveFileName(self, "Save Canvas", "", "PNG Files (*.png)")

        # Save to file 
        if filename:
            pixmap.save(filename)
            print(f"Saved visible canvas to {filename}")

    '''
    SKILL:
    Stamps the North indicator (as drawn by the helper method _create_north_arrow_pixmap) at a size, rotation and colour appropriate to the plot in the viewport.
    '''
    def _stamp_north_arrow(self, pixmap, rotation, facecolour):
        vp_width = pixmap.width()
        vp_height = pixmap.height()
        arrow_size = int(vp_height * 0.05)

        arrow_color = QColor("black") if np.allclose(facecolour, [1.0, 1.0, 1.0]) else QColor("white")
        arrow_pixmap = self._create_north_arrow_pixmap(arrow_size, arrow_color)

        # Rotate arrow pixmap
        transform = QTransform()
        transform.rotate(-rotation)
        rotated_arrow = arrow_pixmap.transformed(transform, Qt.SmoothTransformation)

        # Position in top-right corner
        inset = int(vp_height * 0.05)
        x = vp_width - rotated_arrow.width() - inset
        y = inset

        # Stamp onto original pixmap
        painter = QPainter(pixmap)
        painter.drawPixmap(x, y, rotated_arrow)
        painter.end()

    '''
    SKILL:
    Does the intricate bit of drawing a pretty indicator inside a small pixel map.
    Drawn as though North were Up to keep things simple(r).
    Returns a small pixelmap that can then be rotated and overstamped.
    '''
    @staticmethod
    def _create_north_arrow_pixmap(size, arrow_color):
        arrow_head_height = int(size * 0.4)
        arrow_head_width = int(size * 0.3)

        # Label "N"
        font = QFont()
        font.setPointSizeF(size * 0.2)
        metrics = QFontMetrics(font)
        text_width = int(round(metrics.horizontalAdvance("N")))
        text_height = int(round(metrics.height()))

        height = size + text_height
        width =  max(arrow_head_width, text_width)

        arrow_pixmap = QPixmap(width, height)
        arrow_pixmap.fill(Qt.transparent)

        painter = QPainter(arrow_pixmap)
        painter.setRenderHint(QPainter.Antialiasing)
        pen = QPen(arrow_color)
        pen.setWidth(2)
        painter.setPen(pen)
        painter.setBrush(arrow_color)

        # Arrowhead
        left = (width - arrow_head_width) // 2
        base_left  = QPointF(left, arrow_head_height)
        base_right = QPointF(left + arrow_head_width, arrow_head_height)
        tip = QPointF(width //2, 0)
        arrow_head = QPolygonF([tip, base_left, base_right])
        painter.drawPolygon(arrow_head)

        # Shaft
        tip  = QPointF(width // 2, arrow_head_height)
        base = QPointF(width // 2, height - text_height)
        painter.drawLine(tip, base)

        # Crossbar
        crossbar_pos = height  // 2
        painter.drawLine(
            QPointF(0, crossbar_pos),
            QPointF(width, crossbar_pos)
        )

        # N marker
        painter.setFont(font)
        margin = (width - text_width) // 2
        painter.drawText(QPointF(margin, height), "N")

        painter.end()
        return arrow_pixmap
