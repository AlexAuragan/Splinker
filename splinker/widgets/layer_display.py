from __future__ import annotations

from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core import Palette, Layer, Gradient, dist2, Point, Path
from splinker.widgets.utils import point_to_qpoint


class LayerDisplayComponent(QtWidgets.QWidget):
    """
    Qt widget that directly renders/edits the active Layer of a Palette.
    No per-layer Qt widgets; pure view/controller bound to a pure-Python model.
    """

    pointsChanged = QtCore.Signal()  # emitted whenever path points change (add/move/remove/close)

    def __init__(self, palette: Optional[Palette] = None, parent=None):
        super().__init__(parent)
        self._palette: Optional[Palette] = None
        self._drag_index: Optional[int] = None
        self._hit_radius = 10.0
        self._active = True

        # gradient cache
        self._bg = QtGui.QImage()
        self._bg_dpr: Optional[float] = None

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        if palette is not None:
            self.set_palette(palette)

    # ---------- binding ----------
    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._invalidate_background()
        self.update()

    def clear_palette(self) -> None:
        self._palette = None
        self._invalidate_background()
        self.update()

    # ---------- helpers ----------
    def _layer(self) -> Optional[Layer]:
        if self._palette is None:
            return None
        if self._palette.active_idx < 0 or self._palette.active_idx >= len(self._palette):
            return None
        return self._palette.active_layer

    def _invalidate_background(self):
        self._bg = QtGui.QImage()
        self._bg_dpr = None

    # ---------- size hints ----------
    def sizeHint(self):
        return QtCore.QSize(600, 600)

    def minimumSizeHint(self):
        return QtCore.QSize(200, 200)

    # ---------- gradient cache/render ----------
    def _ensure_bg_current(self):
        dpr = self.devicePixelRatioF()
        if (
            self._bg.isNull()
            or self._bg.width() != int(self.width() * dpr)
            or self._bg.height() != int(self.height() * dpr)
            or self._bg_dpr != dpr
        ):
            self._render_background()

    def _render_background(self):
        dpr = self.devicePixelRatioF()
        w = max(1, int(self.width() * dpr))
        h = max(1, int(self.height() * dpr))

        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)

        lyr = self._layer()
        grad: Optional[Gradient] = None if lyr is None else lyr.gradient
        if grad is not None:
            inv_dpr = 1.0 / dpr
            for y in range(h):
                wy = (y + 0.5) * inv_dpr
                for x in range(w):
                    wx = (x + 0.5) * inv_dpr
                    col_like = grad.color_at(wx, wy)
                    qcol = self._to_qcolor(col_like)
                    if qcol is not None:
                        img.setPixelColor(x, y, qcol)

        self._bg = img
        self._bg_dpr = dpr

    def _to_qcolor(self, col_like):
        if col_like is None:
            return None
        if isinstance(col_like, QtGui.QColor):
            return col_like
        h, s, v, a = col_like.to_hsva()
        return QtGui.QColor.fromHsv(int(h), int(s), int(v), int(a))

    def _contains_point(self, pt: Point) -> bool:
        lyr = self._layer()
        if lyr is None or lyr.gradient is None:
            return False
        return lyr.gradient.contains_point(pt[0], pt[1])

    def _color_at(self, pt: Point) -> Optional[QtGui.QColor]:
        self._ensure_bg_current()
        if self._bg.isNull():
            return None
        dpr = self.devicePixelRatioF()
        x = pt[0] * dpr
        y = pt[1] * dpr
        if x < 0 or y < 0 or x >= self._bg.width() or y >= self._bg.height():
            return None
        return QtGui.QColor.fromRgba(self._bg.pixel(int(x), int(y)))

    # ---------- path editing ----------
    def _index_at(self, pos: Point) -> Optional[int]:
        lyr = self._layer()
        if lyr is None:
            return None
        r2 = self._hit_radius ** 2
        for i, p in enumerate(lyr.path.points):
            if dist2(p, pos) <= r2:
                return i
        return None

    def _can_close_now(self) -> bool:
        lyr = self._layer()
        if lyr is None:
            return False
        return (not lyr.path.closed) and (len(lyr.path.points) >= 3)

    # ---------- Qt events ----------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        lyr = self._layer()
        if lyr is None:
            return

        pos: Point = e.position().toTuple()
        idx = self._index_at(pos)

        # close path on first point
        if (e.button() == QtCore.Qt.MouseButton.LeftButton) and idx == 0 and self._can_close_now():
            lyr.path.closed = True
            self._drag_index = None
            self.pointsChanged.emit()
            self.update()
            return

        # remove point (right click or Ctrl+left)
        is_remove = (
            e.button() == QtCore.Qt.MouseButton.RightButton
            or (e.button() == QtCore.Qt.MouseButton.LeftButton
                and e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier)
        )
        if is_remove and idx is not None:
            lyr.path.remove_point(idx)
            self._drag_index = None
            self.pointsChanged.emit()
            self.update()
            return

        # add or start drag
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            if idx is not None:
                self._drag_index = idx
            else:
                if self._contains_point(pos):
                    old_len = len(lyr.path.points)
                    new_pt = pos
                    lyr.path.add_point(new_pt)
                    # find inserted index
                    if len(lyr.path.points) == old_len + 1:
                        try:
                            self._drag_index = lyr.path.points.index(new_pt)
                        except ValueError:
                            self._drag_index = len(lyr.path.points) - 1
                    else:
                        self._drag_index = len(lyr.path.points) - 1
                    self.pointsChanged.emit()
                    self.update()

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        lyr = self._layer()
        if lyr is None:
            return

        pos = Point(e.position().toTuple())

        if self._drag_index is None:
            idx = self._index_at(pos)
            self.setCursor(
                QtCore.Qt.CursorShape.SizeAllCursor if idx is not None
                else QtCore.Qt.CursorShape.CrossCursor
            )
            return

        if self._contains_point(pos):
            lyr.path.edit_point(self._drag_index, pos)
            self.pointsChanged.emit()
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    # ---------- painting ----------
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        # gradient bg
        self._ensure_bg_current()
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(0, 0, self._bg)

        lyr = self._layer()
        if lyr is None or not lyr.path.points:
            painter.end()
            return

        if not self._active:
            painter.setOpacity(0.5)

        # path stroke
        path = self._make_qpath(lyr.path)
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 2.0)
        painter.setPen(pen)
        painter.drawPath(path)

        # control polygon
        if len(lyr.path.points) >= 2:
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 60), 1.0, QtCore.Qt.PenStyle.DashLine))
            for i in range(len(lyr.path.points) - 1):
                painter.drawLine(point_to_qpoint(lyr.path.points[i]),
                                 point_to_qpoint(lyr.path.points[i + 1]))
            if lyr.path.closed:
                painter.drawLine(point_to_qpoint(lyr.path.points[-1]),
                                 point_to_qpoint(lyr.path.points[0]))

        # control points
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0))
        r = self._hit_radius
        for pt in lyr.path.points:
            painter.drawEllipse(QtCore.QRectF(pt[0] - r * 0.5, pt[1] - r * 0.5, r, r))

        painter.end()

    def _make_qpath(self, path_model: Path) -> QtGui.QPainterPath:
        pts = path_model.points
        closed = path_model.closed
        ops = path_model.editor.path_ops(pts, closed)

        qp = QtGui.QPainterPath()
        qpf = lambda t: QtCore.QPointF(t[0], t[1])

        for op, data in ops:
            if op == "M":
                qp.moveTo(qpf(data))
            elif op == "L":
                qp.lineTo(qpf(data))
            elif op == "C":
                c1, c2, p2 = data
                qp.cubicTo(qpf(c1), qpf(c2), qpf(p2))
            elif op == "Z":
                qp.closeSubpath()
        return qp

    # ---------- API for Canvas ----------
    def notify_active_layer_changed(self):
        """
        Called by the Canvas when the Palette.active_idx changes.
        We just invalidate caches and repaint.
        """
        self._invalidate_background()
        self.update()

    def notify_gradient_changed(self) -> None:
        """
        Call this when the active layer's gradient object changes.
        Forces the background cache to rebuild and repaints.
        """
        self._invalidate_background()
        self.update()

