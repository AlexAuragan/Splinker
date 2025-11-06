from PySide6 import QtWidgets, QtGui
from PySide6.QtGui import QColor

from splinker.core import Color
from splinker.widgets import CanvasWidget


class PaletteGradientBar(QtWidgets.QWidget):
    def __init__(self, overlay: CanvasWidget, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        self.setMinimumWidth(28)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        self._overlay.overlayUpdated.connect(self.update)
        self._overlay.activeLayerChanged.connect(self.update)
        self._overlay.overlaysChanged.connect(self.update)

    def _collect_stops(self, /):
        """
        Returns (stops: list[(pos:float, QColor)], has_data: bool).
        Uses the active path editor's interpolate() to sample the path and
        colors the samples via the gradient widget.
        """
        layer_widget = self._overlay.active_layer
        if layer_widget is None:
            return [], False

        path = layer_widget.path
        pts = path.points
        if not pts:
            return [], False

        # 1) sample along the *actual path* (editor-aware)
        #    keep it modest to avoid hundreds of stops in a tiny bar
        SAMPLES = 64
        samples = path.editor.interpolate(pts, path.closed, n=SAMPLES)
        if not samples or len(samples) < 2:
            return [], False

        # 2) color the samples with the current gradient widget
        if layer_widget is None:
            return [], False
        cols = layer_widget.gradient.points_to_colors(samples)
        if not cols or len(cols) != len(samples):
            return [], False

        # 3) build gradient stops (uniform by sample index -> [0..1])
        stops: list[tuple[float, QtGui.QColor]] = []
        N = len(samples)
        for i in range(N):
            c = cols[i]
            if isinstance(c, Color):
                c = c.to_QColor()
            if c is None:
                continue
            if c.isValid():
                t = i / (N - 1)
                stops.append((t, c))

        # make sure we have at least 2 valid stops
        if len(stops) < 2:
            return [], False

        # clamp/sort just in case (Qt expects non-decreasing positions)
        stops.sort(key=lambda t: t[0])
        return stops, True


    def paintEvent(self, _event):
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, False)

        rect = self.rect()
        p.fillRect(rect, self.palette().window())

        stops, ok = self._collect_stops()
        if not ok or len(stops) < 2:
            # show a faint placeholder
            p.fillRect(rect.adjusted(2, 2, -2, -2), QtGui.QColor(220, 220, 220))
            p.end()
            return

        grad = QtGui.QLinearGradient(rect.center().x(), rect.top(), rect.center().x(), rect.bottom())
        for s, c in stops:
            grad.setColorAt(s, c)

        p.fillRect(rect.adjusted(1, 1, -1, -1), grad)
        # thin frame
        p.setPen(QtGui.QPen(self.palette().mid().color()))
        p.drawRect(rect.adjusted(0, 0, -1, -1))
        p.end()
