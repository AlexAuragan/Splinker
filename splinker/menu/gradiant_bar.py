from PySide6 import QtWidgets, QtCore, QtGui

from splinker.widgets import Overlay


class PaletteGradientBar(QtWidgets.QWidget):
    def __init__(self, overlay: Overlay, parent=None):
        super().__init__(parent)
        self._overlay = overlay
        self.setMinimumWidth(28)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Fixed, QtWidgets.QSizePolicy.Policy.Expanding)
        self._overlay.overlayUpdated.connect(lambda *_: self.update())
        self._overlay.activeLayerChanged.connect(lambda *_: self.update())
        self._overlay.overlaysChanged.connect(self.update)


    def _poly_length_positions(self, pts: list[QtCore.QPointF], closed: bool, /) -> list[float]:
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
            dx = float(pts[i + 1].x() - pts[i].x())
            dy = float(pts[i + 1].y() - pts[i].y())
            d = (dx*dx + dy*dy) ** 0.5
            total += d
            lens.append(total)

        # Close if needed
        if closed and n >= 2:
            dx = float(pts[0].x() - pts[-1].x())
            dy = float(pts[0].y() - pts[-1].y())
            total += (dx*dx + dy*dy) ** 0.5

        if total <= 0.0:
            return [0.0 for _ in range(n)]

        return [min(1.0, (s / total)) for s in lens]

    def _collect_stops(self, /):
        """
        Returns (stops: list[(pos:float, QColor)], has_data: bool).
        Falls back to uniform spacing if lengths degenerate.
        """
        if self._overlay.spline is None:
            return [], False

        # points (list) and colors (list[QColor|None])
        pts_get = getattr(self._overlay.spline, "points", None)
        pts = pts_get() if callable(pts_get) else getattr(self._overlay.spline, "_points", None)
        pts = pts or []

        col_get = getattr(self._overlay.spline, "point_colors", None)
        if callable(col_get):
            try:
                cols = col_get()
            except Exception:
                cols = None
        else:
            cols = None

        # if missing, compute colors via gradient sampling when possible
        if cols is None:
            cols = []
            grad = getattr(self._overlay.spline, "_gradient", None)
            sampler = getattr(grad, "color_at", None) if grad is not None else None
            if callable(sampler):
                for p in pts:
                    cols.append(sampler(p))
            else:
                # give up -> no data
                return [], False

        # filter invalid colors but keep positions aligned
        ok_idx = [i for i, c in enumerate(cols) if isinstance(c, QtGui.QColor) and c.isValid()]
        if not ok_idx:
            return [], False

        closed = bool(getattr(self._overlay.spline, "_closed", False))
        pos = self._poly_length_positions(pts, closed) if len(pts) >= 2 else [0.0]

        # if lengths failed, fall back to uniform
        if len(pos) != len(pts) or (len(pts) >= 2 and all(abs(p) < 1e-9 for p in pos[1:])):
            pos = [i / max(1, (len(pts) - 1)) for i in range(len(pts))]

        stops: list[tuple[float, QtGui.QColor]] = []
        for i in ok_idx:
            p = 0.0 if i >= len(pos) else float(pos[i])
            stops.append((p, cols[i]))

        # if closed and first/last positions far apart, optionally add wrap stop
        if closed and len(stops) >= 2:
            p0, c0 = stops[0]
            pN, cN = stops[-1]
            if pN < 1.0:
                stops.append((1.0, cN))
            if p0 > 0.0:
                stops.insert(0, (0.0, c0))

        # clamp/sort
        stops = [(0.0 if s < 0.0 else (1.0 if s > 1.0 else s), c) for s, c in stops]
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
