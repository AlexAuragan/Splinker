from typing import Optional, override

from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core import Palette, Layer, dist2, Point
from splinker.widgets.utils import point_to_qpoint


class PathEditorDisplayComponent(QtWidgets.QWidget):
    """
    Qt widget that directly renders/edits the active Layer of a Palette.
    No per-layer Qt widgets; pure view/controller bound to a pure-Python model.
    """

    pointsChanged = QtCore.Signal()  # emitted whenever path points change (add/move/remove/close)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette
        self._drag_index: Optional[int] = None
        self._hit_radius = 10.0
        self._active = True

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        self.pointsChanged.connect(self.update)


    # ---------- binding ----------
    @override
    def update(self):
        return self.parent().update()

    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.update()

    def clear_palette(self) -> None:
        self._palette = None
        self.update()

    def activate(self):
        self._active = True
        self.update()

    def deactivate(self):
        self._active = False
        self.update()

    # ---------- helpers ----------
    def _layer(self) -> Layer:
        return self._palette.active_layer

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
    def mouse_press_event(self, e: QtGui.QMouseEvent):
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
                if self._palette.contains_point(pos):
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

    def mouse_move_event(self, e: QtGui.QMouseEvent):
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

        if self._palette.contains_point(pos):
            lyr.path.edit_point(self._drag_index, pos)
            self.pointsChanged.emit()
            self.update()

    def mouse_release_event(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    def _draw_spline(self, painter, path):
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 2.0)
        painter.setPen(pen)
        painter.drawPath(path.make_qpath())

    def _draw_polygon(self, painter, path):
        if len(path.points) >= 2:
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 60), 1.0, QtCore.Qt.PenStyle.DashLine))
            for i in range(len(path.points) - 1):
                painter.drawLine(point_to_qpoint(path.points[i]),
                                 point_to_qpoint(path.points[i + 1]))
            if path.closed:
                painter.drawLine(point_to_qpoint(path.points[-1]),
                                 point_to_qpoint(path.points[0]))

    def _draw_control(self, painter, path):
        painter.setBrush(QtGui.QColor(255, 255, 255, 230))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0))
        r = self._hit_radius
        for pt in path.points:
            painter.drawEllipse(QtCore.QRectF(pt[0] - r * 0.5, pt[1] - r * 0.5, r, r))


    # ---------- painting ----------
    def paint_event(self, painter, event):

        # gradient bg
        lyr = self._layer()
        if lyr is None or not lyr.path.points:
            painter.end()
            return

        if self._active:
            self._draw_spline(painter, lyr.path)
            self._draw_polygon(painter, lyr.path)
            self._draw_control(painter, lyr.path)
        else:
            # painter.setOpacity(0.5)
            self._draw_spline(painter, lyr.path)

        # control points

        painter.end()

    # ---------- API for Canvas ----------
    def notify_active_layer_changed(self):
        """
        Called by the Canvas when the Palette.active_idx changes.
        We just invalidate caches and repaint.
        """
        self.update()

