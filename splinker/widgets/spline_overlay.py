from PySide6 import QtCore, QtGui, QtWidgets

from splinker.widgets.gradients_overlay import GradientOverlayWidget
from splinker.core.splines import Spline, CatmullRomSpline


class SplineOverlayWidget(QtWidgets.QWidget):
    """
    Transparent overlay that edits and draws a path on top of a GradientWidget.

    A single widget class that delegates spline computation to an injected
    `Spline` (from splinker.splines). Everything else (point management,
    gestures, constraints, painting) remains here.
    """

    pointsChanged = QtCore.Signal()

    def __init__(self, gradient: GradientOverlayWidget, spline_type: Spline | None = None, parent=None):
        super().__init__(parent or gradient.parent())
        self._gradient = gradient
        self._spline = spline_type or CatmullRomSpline()

        self._points: list[QtCore.QPointF] = []
        self._drag_index: int | None = None
        self._hit_radius = 8.0
        self._closed = False
        self._active = True

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.raise_()
        self._sync_geometry()
        self._gradient.installEventFilter(self)

    # ----- activation API ----------------------------------------------------
    def is_active(self, /) -> bool:
        return self._active

    def is_closed(self):
        return self._closed

    def deactivate(self, /):
        """
        Make the overlay non-interactive and half transparent.
        Mouse events pass through to widgets below.
        """
        if not self._active:
            return
        self._active = False
        self._drag_index = None
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setCursor(QtCore.Qt.CursorShape.ArrowCursor)
        self.update()

    def activate(self, /):
        """
        Reactivate editing and restore full opacity.
        """
        if self._active:
            return
        self._active = True
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.update()

    # ----- public API --------------------------------------------------------
    @property
    def points(self):
        return self._points

    def update(self, /):
        QtWidgets.QWidget.update(self)
        self._emit_points_changed()

    def is_closed(self, /) -> bool:
        return self._closed

    def set_closed(self, closed: bool, /):
        if self._closed != closed:
            self._closed = closed
            self.update()

    def clear(self, /):
        self._points.clear()
        self._closed = False
        self._drag_index = None
        self.update()

    # ----- plumbing ----------------------------------------------------------
    def _sync_geometry(self):
        self.setParent(self._gradient.parent())
        self.setGeometry(self._gradient.geometry())
        self.raise_()

    def eventFilter(self, obj, event):
        if obj is self._gradient:
            t = event.type()
            if t in (QtCore.QEvent.Type.Move, QtCore.QEvent.Type.Resize):
                self._sync_geometry()
            elif t == QtCore.QEvent.Type.Show:
                self.show()
            elif t == QtCore.QEvent.Type.Hide:
                self.hide()
        return super().eventFilter(obj, event)

    # ----- interaction helpers ----------------------------------------------
    def _dist2(self, a: QtCore.QPointF, b: QtCore.QPointF, /) -> float:
        dx = float(a.x() - b.x())
        dy = float(a.y() - b.y())
        return dx * dx + dy * dy

    def _index_at(self, pos: QtCore.QPointF) -> int | None:
        r2 = self._hit_radius * self._hit_radius
        for i, p in enumerate(self._points):
            if self._dist2(p, pos) <= r2:
                return i
        return None

    def _near_endpoint(self, pos: QtCore.QPointF, /) -> int | None:
        if len(self._points) < 1:
            return None
        r2 = (self._hit_radius * 1.5) ** 2
        if self._dist2(pos, self._points[0]) <= r2:
            return 0
        if len(self._points) >= 2 and self._dist2(pos, self._points[-1]) <= r2:
            return -1
        return None

    def _ensure_closed_valid(self, /):
        if self._closed and len(self._points) < 3:
            self._closed = False

    def _maybe_close_path(self, pos: QtCore.QPointF, /) -> bool:
        if self._closed or len(self._points) < 3:
            return False
        hit = self._near_endpoint(pos)
        if hit is None:
            return False

        self._closed = True
        self.update()
        return True

    def _constrain_to_gradient(self, pos: QtCore.QPointF) -> QtCore.QPointF | None:
        return pos if self._gradient.contains_point(pos) else None

    # ----- mouse events ------------------------------------------------------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        pos = QtCore.QPointF(e.position())

        if e.button() == QtCore.Qt.MouseButton.LeftButton and self._maybe_close_path(pos):
            return

        is_remove = (e.button() == QtCore.Qt.MouseButton.RightButton) or \
                    (e.button() == QtCore.Qt.MouseButton.LeftButton and e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)

        idx = self._index_at(pos)

        if is_remove:
            if idx is not None:
                self._points.pop(idx)
                self._drag_index = None
                self._ensure_closed_valid()
                self.update()
            return

        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            if idx is not None:
                self._drag_index = idx
            else:
                inside = self._constrain_to_gradient(pos)
                if inside is not None:
                    if self._closed and len(self._points) >= 3:
                        if self.insert_point_convex(inside):
                            self._drag_index = None
                            self.update()
                            return
                    self._points.append(inside)
                    self._drag_index = len(self._points) - 1
                    self._ensure_closed_valid()
                    self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if self._drag_index is None:
            idx = self._index_at(QtCore.QPointF(e.position()))
            self.setCursor(QtCore.Qt.CursorShape.SizeAllCursor if idx is not None else QtCore.Qt.CursorShape.CrossCursor)
            return
        pos = QtCore.QPointF(e.position())
        inside = self._constrain_to_gradient(pos)
        if inside is not None:
            self._points[self._drag_index] = inside
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    def _make_path(self, pts: list[QtCore.QPointF], closed: bool, /) -> QtGui.QPainterPath:
        n = len(pts)
        if n == 0:
            return QtGui.QPainterPath()

        # Convert to tuples for backend
        as_tuples = [(float(p.x()), float(p.y())) for p in pts]
        ops = list(self._spline.path_ops(as_tuples, closed))

        # Adapt ops -> QPainterPath
        def qpf(t): return QtCore.QPointF(t[0], t[1])

        # Find initial move
        path = QtGui.QPainterPath()
        for op, data in ops:
            if op == "M":
                path.moveTo(qpf(data))
            elif op == "L":
                path.lineTo(qpf(data))
            elif op == "C":
                c1, c2, p2 = data
                path.cubicTo(qpf(c1), qpf(c2), qpf(p2))
            elif op == "Z":
                path.closeSubpath()
        return path

    # ----- painting ----------------------------------------------------------
    def paintEvent(self, _event):
        if not self._points:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        # Half transparency when inactive
        if not self._active:
            p.setOpacity(0.5)

        path = self._make_path(self._points, self._closed)
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 2.0,
                         QtCore.Qt.PenStyle.SolidLine,
                         QtCore.Qt.PenCapStyle.RoundCap,
                         QtCore.Qt.PenJoinStyle.RoundJoin)
        p.setPen(pen)
        p.drawPath(path)

        if len(self._points) >= 2:
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 60), 1.0, QtCore.Qt.PenStyle.DashLine))
            for i in range(len(self._points) - 1):
                p.drawLine(self._points[i], self._points[i + 1])
            if self._closed:
                p.drawLine(self._points[-1], self._points[0])

        p.setBrush(QtGui.QColor(255, 255, 255, 230))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0))
        r = self._hit_radius
        for pt in self._points:
            p.drawEllipse(QtCore.QRectF(pt.x() - r * 0.5, pt.y() - r * 0.5, r, r))

        p.end()

    def insert_point_convex(self, p: QtCore.QPointF, /) -> bool:
        """
        Delegate to backend; preserves widget behavior (mutates self._points).
        """
        if not self._closed or len(self._points) < 3:
            return False

        as_tuples = [(float(t.x()), float(t.y())) for t in self._points]
        new_pts, ok = self._spline.insert_point_convex(as_tuples, (float(p.x()), float(p.y())), True)
        if not ok:
            return False

        # apply mutation in-place
        self._points[:] = [QtCore.QPointF(x, y) for (x, y) in new_pts]
        return True

    # ----- color sampling helpers (unchanged) --------------------------------
    def point_to_color(self, pt: QtCore.QPointF, /) -> QtGui.QColor | None:
        if not self._gradient.contains_point(pt):
            return None
        return self._gradient.color_at(pt)

    def point_colors(self, /) -> list[QtGui.QColor | None]:
        out: list[QtGui.QColor | None] = []
        for p in self._points:
            out.append(self.point_to_color(p))
        return out

    def move_point_to_color(self, index: int, color: QtGui.QColor, /) -> bool:
        if index < 0 or index >= len(self._points):
            return False
        pt = self._gradient.point_for_color(color)
        if pt is None or not self._gradient.contains_point(pt):
            return False
        self._points[index] = QtCore.QPointF(pt)
        self.update()
        return True

    # ----- Signals -----------------------------------------------------------
    def _emit_points_changed(self, /):
        self.pointsChanged.emit()

