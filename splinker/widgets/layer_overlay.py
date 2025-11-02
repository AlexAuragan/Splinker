from typing import override

from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core.layer import Layer
from splinker.core.gradients import Gradient, HsvSquareGradient
from splinker.core.path import Path
from splinker.core.point_editors import CatmullRomSplinePE
from splinker.core import Point
from splinker.widgets.utils import point_to_qpoint


class LayerOverlayWidget(QtWidgets.QWidget):
    """
    Unified widget combining gradient rendering and path editing.
    Directly maps to a Layer dataclass (gradient + path + name).
    """

    pointsChanged = QtCore.Signal()

    def __init__(self, layer: Layer | None = None, parent=None):
        super().__init__(parent)

        # Initialize with provided layer or create default
        if layer is None:
            layer = Layer(
                gradient=HsvSquareGradient(300, 300, 298, hue=0),
                path=Path(editor=CatmullRomSplinePE()),
                name="New Layer"
            )
        self._layer = layer

        # Path editing state
        self._drag_index: int | None = None
        self._hit_radius = 8.0
        self._active = True

        # Gradient rendering cache
        self._bg = QtGui.QImage()
        self._bg_dpr: float | None = None
        self._pad = 2

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    # ---- Layer access -------------------------------------------------------
    @property
    def layer(self) -> Layer:
        """Direct access to the underlying Layer dataclass."""
        return self._layer

    @property
    def gradient(self) -> Gradient:
        """Convenience accessor for the layer's gradient."""
        return self._layer.gradient

    @property
    def path(self) -> Path:
        """Convenience accessor for the layer's path."""
        return self._layer.path

    @property
    def points(self):
        """Convenience accessor for path points."""
        return self._layer.path.points

    @property
    def name(self) -> str:
        """Convenience accessor for layer name."""
        return self._layer.name

    def set_gradient(self, gradient: Gradient):
        """Replace the gradient and invalidate cache."""
        self._layer.gradient = gradient
        self._bg = QtGui.QImage()
        self._bg_dpr = None
        self.update()

    def set_name(self, name: str):
        """Update the layer name."""
        self._layer.name = name

    def clear_path(self):
        """Clear all points from the path."""
        self._layer.path.clear()
        self.update()

    # ---- Size hints ---------------------------------------------------------
    def sizeHint(self):
        return QtCore.QSize(600, 600)

    def minimumSize(self):
        return QtCore.QSize(200, 200)

    # ---- Gradient rendering -------------------------------------------------
    def render_background(self):
        """
        Render the gradient into a cached image.
        Samples the gradient at each pixel in widget space.
        """
        dpr = self.devicePixelRatioF()
        w = max(1, int(self.width() * dpr))
        h = max(1, int(self.height() * dpr))

        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)  # fully transparent

        grad = self._layer.gradient
        if grad is None:
            self._bg = img
            self._bg_dpr = dpr
            return

        # Sample at pixel centers in widget coordinates
        inv_dpr = 1.0 / dpr

        for y in range(h):
            wy = (y + 0.5) * inv_dpr
            for x in range(w):
                wx = (x + 0.5) * inv_dpr
                col_like = grad.color_at(wx, wy)
                qcol = self._to_qcolor(col_like)
                if qcol is not None:
                    img.setPixelColor(x, y, qcol)
                # else leave transparent

        self._bg = img
        self._bg_dpr = dpr

    def _ensure_bg_current(self):
        """Ensure the cached background matches current size/DPR."""
        dpr = self.devicePixelRatioF()
        if (self._bg.isNull()
                or self._bg.width() != int(self.width() * dpr)
                or self._bg.height() != int(self.height() * dpr)
                or self._bg_dpr != dpr):
            self.render_background()

    def _to_qcolor(self, col_like):
        """
        Convert color-like object to QColor.
        Accepts: QColor, object with .get_hsva(), 4-tuple (h,s,v,a), or None.
        """
        if col_like is None:
            return None
        if isinstance(col_like, QtGui.QColor):
            return col_like

        h, s, v, a = col_like.to_hsva()
        return QtGui.QColor.fromHsv(int(h), int(s), int(v), int(a))

    # ---- Gradient queries ---------------------------------------------------
    def contains_point(self, pt: QtCore.QPointF) -> bool:
        """Check if point is within gradient bounds."""
        grad = self._layer.gradient
        if grad is None:
            return False
        return bool(grad.contains_point(float(pt.x()), float(pt.y())))

    def color_at(self, pt: QtCore.QPointF) -> QtGui.QColor | None:
        """Sample color at widget-space point from cached gradient."""
        self._ensure_bg_current()
        if self._bg.isNull():
            return None
        dpr = self.devicePixelRatioF()
        x = int(float(pt.x()) * dpr)
        y = int(float(pt.y()) * dpr)
        if x < 0 or y < 0 or x >= self._bg.width() or y >= self._bg.height():
            return None
        return QtGui.QColor.fromRgba(self._bg.pixel(x, y))

    def point_colors(self) -> list[QtGui.QColor]:
        """Get colors for all path points."""
        self._ensure_bg_current()
        colors = []
        for p in self._layer.path.points:
            pt = QtCore.QPointF(p[0], p[1])
            colors.append(self.color_at(pt))
        return colors

    def point_for_color(self, color: QtGui.QColor):
        """Find widget-space point for a given color (reverse lookup)."""
        grad = self._layer.gradient
        if grad is None:
            return None

        # Adapt QColor -> HSVa object
        h, s, v, a = color.getHsv()
        adapter = self._HSVaAdapter(h, s, v, a)
        pt = grad.point_at(adapter)
        if pt is None:
            return None
        x, y = pt
        qpt = QtCore.QPointF(float(x), float(y))
        return qpt if self.contains_point(qpt) else None

    class _HSVaAdapter:
        """Adapter for QColor -> gradient color format."""

        def __init__(self, h, s, v, a):
            self._hsva = (int(h), int(s), int(v), int(a))

        def get_hsva(self):
            return self._hsva

    # ---- Path editing helpers -----------------------------------------------
    def _dist2(self, a: QtCore.QPointF, b: QtCore.QPointF) -> float:
        """Squared distance between two points."""
        dx = float(a.x() - b.x())
        dy = float(a.y() - b.y())
        return dx * dx + dy * dy

    def _index_at(self, pos: QtCore.QPointF) -> int | None:
        """Find index of point at position, or None."""
        r2 = self._hit_radius ** 2
        for i, p in enumerate(self._layer.path.points):
            if self._dist2(point_to_qpoint(p), pos) <= r2:
                return i
        return None

    def _constrain_to_gradient(self, pos: QtCore.QPointF) -> QtCore.QPointF | None:
        """Return pos if within gradient, else None."""
        return pos if self.contains_point(pos) else None

    def _can_close_now(self) -> bool:
        """Check if path can be closed (3+ points and not already closed)."""
        return (not self._layer.path.closed) and (len(self._layer.path.points) >= 3)

    # ---- Mouse events -------------------------------------------------------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return

        pos = QtCore.QPointF(e.position())
        idx = self._index_at(pos)

        # Close path by clicking first point
        if (e.button() == QtCore.Qt.MouseButton.LeftButton
                and idx == 0
                and self._can_close_now()):
            self._layer.path.closed = True
            self._drag_index = None
            self.update()
            return

        # Remove point (right-click or Ctrl+click)
        is_remove = (
                e.button() == QtCore.Qt.MouseButton.RightButton
                or (e.button() == QtCore.Qt.MouseButton.LeftButton
                    and e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        )

        if is_remove and idx is not None:
            self._layer.path.remove_point(idx)
            self._drag_index = None
            self.update()
            return

        # Add or start dragging point
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            if idx is not None:
                self._drag_index = idx
            else:
                inside = self._constrain_to_gradient(pos)
                if inside is not None:
                    old_closed = self._layer.path.closed
                    old_len = len(self._layer.path.points)
                    new_pt = (inside.x(), inside.y())

                    self._layer.path.add_point(new_pt)

                    # Find inserted index
                    if old_closed and len(self._layer.path.points) == old_len + 1:
                        try:
                            self._drag_index = self._layer.path.points.index(new_pt)
                        except ValueError:
                            self._drag_index = len(self._layer.path.points) - 1
                    else:
                        self._drag_index = len(self._layer.path.points) - 1

                    self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return

        pos = QtCore.QPointF(e.position())

        if self._drag_index is None:
            # Update cursor based on hover
            idx = self._index_at(pos)
            self.setCursor(
                QtCore.Qt.CursorShape.SizeAllCursor if idx is not None
                else QtCore.Qt.CursorShape.CrossCursor
            )
            return

        # Drag point
        inside = self._constrain_to_gradient(pos)
        if inside is not None:
            self._layer.path.edit_point(self._drag_index, (inside.x(), inside.y()))
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    # ---- Painting -----------------------------------------------------------
    def _make_path(self) -> QtGui.QPainterPath:
        """Convert path points to QPainterPath using the path's editor."""
        pts = self._layer.path.points
        closed = self._layer.path.closed
        ops = self._layer.path.editor.path_ops(pts, closed)

        path = QtGui.QPainterPath()
        qpf = lambda t: QtCore.QPointF(t[0], t[1])

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

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        # 1. Render gradient background
        if (self._bg.isNull()
                or self._bg.width() != int(self.width() * self.devicePixelRatioF())
                or self._bg.height() != int(self.height() * self.devicePixelRatioF())
                or self._bg_dpr != self.devicePixelRatioF()):
            self.render_background()

        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(0, 0, self._bg)

        # 2. Draw path overlay (if points exist)
        if not self._layer.path.points:
            painter.end()
            return

        if not self._active:
            painter.setOpacity(0.5)

        # Draw the spline curve
        path = self._make_path()
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 2.0)
        painter.setPen(pen)
        painter.drawPath(path)

        # Draw control polygon (dashed lines between points)
        if len(self._layer.path.points) >= 2:
            painter.setPen(QtGui.QPen(
                QtGui.QColor(0, 0, 0, 60),
                1.0,
                QtCore.Qt.PenStyle.DashLine
            ))
            for i in range(len(self._layer.path.points) - 1):
                painter.drawLine(
                    point_to_qpoint(self._layer.path.points[i]),
                    point_to_qpoint(self._layer.path.points[i + 1])
                )
            if self._layer.path.closed:
                painter.drawLine(
                    point_to_qpoint(self._layer.path.points[-1]),
                    point_to_qpoint(self._layer.path.points[0])
                )

        # Draw control points
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0))
        r = self._hit_radius
        for pt in self._layer.path.points:
            painter.drawEllipse(QtCore.QRectF(
                pt[0] - r * 0.5,
                pt[1] - r * 0.5,
                r, r
            ))

        painter.end()

    # ---- Qt overrides -------------------------------------------------------
    @override
    def update(self):
        self._emit_points_changed()
        super().update()

    def _emit_points_changed(self):
        self.pointsChanged.emit()