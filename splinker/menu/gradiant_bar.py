from PySide6 import QtWidgets, QtGui

from splinker.core import Point
from splinker.widgets import CanvasWidget


class PaletteGradientBar(QtWidgets.QWidget):
    def __init__(self, overlay: CanvasWidget, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        self.setMinimumWidth(28)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        self._overlay.overlayUpdated.connect(lambda *_: self.update())
        self._overlay.activeLayerChanged.connect(lambda *_: self.update())
        self._overlay.overlaysChanged.connect(self.update)


    def _poly_length_positions(self, pts: list[Point], closed: bool, /) -> list[float]:
        """
        Cumulative positions along the control polyline, normalized to [0,1].
        If closed, includes closing edge.
        """
        n = len(pts)
        if n == 0:
            return []
        if n == 1:
            return [0.0]

        lens: list[float] = [0.0]
        total = 0.0
        for i in range(n - 1):
            dx = float(pts[i + 1][0] - pts[i][0])
            dy = float(pts[i + 1][1]  - pts[i][1])
            d = (dx*dx + dy*dy) ** 0.5
            total += d
            lens.append(total)

        # Close if needed
        if closed and n >= 2:
            dx = float(pts[0][0]  - pts[-1][0])
            dy = float(pts[0][1] - pts[-1][1])
            total += (dx*dx + dy*dy) ** 0.5

        if total <= 0.0:
            return [0.0 for _ in range(n)]

        return [min(1.0, (s / total)) for s in lens]

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
            if isinstance(c, QtGui.QColor) and c.isValid():
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
