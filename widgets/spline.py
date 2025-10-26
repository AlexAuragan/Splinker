from abc import ABC, abstractmethod
from PySide6 import QtCore, QtGui, QtWidgets

from widgets.gradients import GradientWidget
from widgets.utils import ABCQtMeta


class AbstractSplineOverlayWidget(QtWidgets.QWidget, ABC, metaclass=ABCQtMeta):
    """
    Transparent overlay that edits and draws a path on top of a GradientWidget.

    Subclasses provide the path construction by implementing `make_path(pts, closed)`.
    This base handles:
      - point management (add/select/drag/remove),
      - loop/close gesture (click near an endpoint),
      - constraining points to the gradient via GradientWidget.contains_point,
      - painting of control polygon and points.
    """

    pointsChanged = QtCore.Signal()
    def __init__(self, gradient: GradientWidget, parent=None):
        super().__init__(parent or gradient.parent())
        self._gradient = gradient
        self._points: list[QtCore.QPointF] = []
        self._drag_index: int | None = None
        self._hit_radius = 8.0
        self._closed = False

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.raise_()
        self._sync_geometry()
        self._gradient.installEventFilter(self)

    # ----- abstract API ------------------------------------------------------
    @abstractmethod
    def make_path(self, pts: list[QtCore.QPointF], closed: bool, /) -> QtGui.QPainterPath:
        """
        Return a QPainterPath from control points in widget coordinates.
        """

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
                        if self._insert_point_convex(inside):
                            self._drag_index = None  # optional: don't auto-drag projected insert
                            self.update()
                            return
                    self._points.append(inside)
                    self._drag_index = len(self._points) - 1
                    self._ensure_closed_valid()
                    self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
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
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    # ----- painting ----------------------------------------------------------
    def paintEvent(self, _event):
        if not self._points:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        path = self.make_path(self._points, self._closed)
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

    def _orientation(self, a: QtCore.QPointF, b: QtCore.QPointF, c: QtCore.QPointF, /) -> float:
        # cross((b-a), (c-b)) > 0 => left turn (CCW), < 0 => right turn (CW)
        return (b.x() - a.x()) * (c.y() - b.y()) - (b.y() - a.y()) * (c.x() - b.x())

    def _signed_area(self, pts: list[QtCore.QPointF], /) -> float:
        n = len(pts)
        if n < 3:
            return 0.0
        s = 0.0
        for i in range(n):
            j = (i + 1) % n
            s += pts[i].x() * pts[j].y() - pts[j].x() * pts[i].y()
        return 0.5 * s

    def _poly_orientation_sign(self, /) -> int:
        # +1 -> CCW, -1 -> CW, 0 -> degenerate
        area = self._signed_area(self._points)
        return 1 if area > 0 else (-1 if area < 0 else 0)

    def _edge_valid_for_convex_insert(self, i: int, p: QtCore.QPointF, sgn: int, /) -> bool:
        """
        Check if inserting p between v[i] and v[i+1] keeps polygon convex
        with respect to global orientation 'sgn' (±1).
        Tests local convexity on the three affected vertices.
        """
        v = self._points
        n = len(v)
        im1 = (i - 1) % n
        ip1 = (i + 1) % n
        ip2 = (i + 2) % n

        # We need these orientations to keep the same sign as sgn
        # (vi-1, vi, p), (vi, p, vi+1), (p, vi+1, vi+2)
        o1 = self._orientation(v[im1], v[i],   p)
        o2 = self._orientation(v[i],   p,      v[ip1])
        o3 = self._orientation(p,      v[ip1], v[ip2])

        # Allow slight numerical tolerance (>= 0 for sgn>0; <=0 for sgn<0)
        if sgn > 0:
            return (o1 >= 0.0) and (o2 >= 0.0) and (o3 >= 0.0)
        else:
            return (o1 <= 0.0) and (o2 <= 0.0) and (o3 <= 0.0)

    def _edge_delta_len(self, a: QtCore.QPointF, b: QtCore.QPointF, p: QtCore.QPointF, /) -> float:
        # Perimeter increase if we split (a,b) by p
        def d(u: QtCore.QPointF, v: QtCore.QPointF) -> float:
            dx = float(u.x() - v.x())
            dy = float(u.y() - v.y())
            return (dx*dx + dy*dy) ** 0.5
        return d(a, p) + d(p, b) - d(a, b)

    def _best_convex_insert_index(self, p: QtCore.QPointF, /) -> int | None:
        """
        Return edge index i such that inserting after i (between v[i] and v[i+1])
        keeps convexity and minimally increases perimeter. None if no edge works.
        """
        v = self._points
        n = len(v)
        if n < 3 or not self._closed:
            return None
        sgn = self._poly_orientation_sign()
        if sgn == 0:
            return None

        best_i = None
        best_delta = float("inf")
        for i in range(n):
            j = (i + 1) % n
            if self._edge_valid_for_convex_insert(i, p, sgn):
                dl = self._edge_delta_len(v[i], v[j], p)
                if dl < best_delta:
                    best_delta = dl
                    best_i = i
        return best_i

    def _project_point_to_segment(self, p: QtCore.QPointF, a: QtCore.QPointF, b: QtCore.QPointF, /) -> QtCore.QPointF:
        ax, ay = float(a.x()), float(a.y())
        bx, by = float(b.x()), float(b.y())
        px, py = float(p.x()), float(p.y())
        vx, vy = bx - ax, by - ay
        denom = vx*vx + vy*vy
        if denom == 0.0:
            return a
        t = ((px - ax) * vx + (py - ay) * vy) / denom
        t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
        return QtCore.QPointF(ax + t * vx, ay + t * vy)

    def _insert_point_convex(self, p: QtCore.QPointF, /) -> bool:
        """
        Try to insert p to keep polygon convex.
        Returns True on success (inserted), False if unable.
        If no convex-preserving edge exists, falls back to projecting onto the nearest edge,
        which guarantees a valid convex insertion.
        """
        v = self._points
        n = len(v)
        if not self._closed or n < 3:
            return False

        # 1) Try a true convex-preserving insertion
        i = self._best_convex_insert_index(p)
        if i is not None:
            self._points.insert(i + 1, p)
            return True

        # 2) Fallback: project to closest edge, then insert there (keeps convexity)
        #    because projected point lies on the boundary.
        best_i = 0
        best_d2 = float("inf")
        best_q = None
        for k in range(n):
            j = (k + 1) % n
            q = self._project_point_to_segment(p, v[k], v[j])
            dx = float(q.x() - p.x())
            dy = float(q.y() - p.y())
            d2 = dx*dx + dy*dy
            if d2 < best_d2:
                best_d2 = d2
                best_i = k
                best_q = q
        if best_q is not None:
            self._points.insert(best_i + 1, best_q)
            return True

        return False

    def point_to_color(self, pt: QtCore.QPointF, /) -> QtGui.QColor | None:
        """
        Return the color at 'pt' if it lies within the gradient; otherwise None.
        """
        if not self._gradient.contains_point(pt):
            return None
        return self._gradient.color_at(pt)

    def point_colors(self, /) -> list[QtGui.QColor | None]:
        """
        Colors for all control points (None for points outside the gradient).
        Useful to feed a menu or palette list.
        """
        out: list[QtGui.QColor | None] = []
        for p in self._points:
            out.append(self.point_to_color(p))
        return out


    def move_point_to_color(self, index: int, color: QtGui.QColor, /) -> bool:
        """
        Try to move control point 'index' so that sampling the gradient at its new
        position yields approximately 'color'. Returns True on success.
        If neither exists, returns False.
        """
        if index < 0 or index >= len(self._points):
            return False

        pt = self._gradient.point_for_color(color)
        if pt is None or not self._gradient.contains_point(pt):
            return False

        self._points[index] = QtCore.QPointF(pt)
        self.update()
        return True

    # ----- Signals ----------------------------------------------------------
    def _emit_points_changed(self, /):
        self.pointsChanged.emit()

# -----------------------------------------------------------------------------
# Concrete implementation: Catmull–Rom spline → cubic Bézier path
# -----------------------------------------------------------------------------

class CatmullRomSplineOverlayWidget(AbstractSplineOverlayWidget):
    def make_path(self, pts: list[QtCore.QPointF], closed: bool, /) -> QtGui.QPainterPath:
        n = len(pts)
        if n == 1:
            return QtGui.QPainterPath(pts[0])
        if n == 2 and not closed:
            path = QtGui.QPainterPath(pts[0])
            path.lineTo(pts[1])
            return path

        # Duplicate neighbors at the ends (open) or wrap (closed)
        if closed:
            p = [pts[-1]] + pts + [pts[0], pts[1]]
        else:
            p = [pts[0]] + pts + [pts[-1]]

        path = QtGui.QPainterPath(pts[0])

        # Walk triplets and emit cubic segments
        for i in range(1, len(p) - 2):
            p0, p1, p2, p3 = p[i - 1], p[i], p[i + 1], p[i + 2]
            c1 = QtCore.QPointF(
                p1.x() + (p2.x() - p0.x()) / 6.0,
                p1.y() + (p2.y() - p0.y()) / 6.0
            )
            c2 = QtCore.QPointF(
                p2.x() - (p3.x() - p1.x()) / 6.0,
                p2.y() - (p3.y() - p1.y()) / 6.0
            )
            path.cubicTo(c1, c2, p2)

        if closed:
            path.closeSubpath()

        return path



