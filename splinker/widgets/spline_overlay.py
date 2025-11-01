from typing import override

from PySide6 import QtCore, QtGui, QtWidgets
from splinker.widgets.gradients_overlay import GradientOverlayWidget
from splinker.core.path import Path
from splinker.core.point_editors import CatmullRomSplinePE
from splinker.widgets.utils import point_to_qpoint


class SplineOverlayWidget(QtWidgets.QWidget):
    pointsChanged = QtCore.Signal()

    def __init__(self, gradient: GradientOverlayWidget, parent=None):
        super().__init__(parent or gradient.parent())
        self._gradient = gradient
        self._path = Path(editor=CatmullRomSplinePE())
        self._drag_index: int | None = None
        self._hit_radius = 8.0
        self._active = True

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)
        self.raise_()
        self._sync_geometry()
        self._gradient.installEventFilter(self)


    # ---- convenience accessors ---------------------------------------------
    @property
    def points(self):
        return self._path.points

    def clear(self):
        self._path.clear()

    def point_colors(self):
        return self._gradient.colors_for_points(self._path.points)

    # ---- Qt plumbing --------------------------------------------------------
    @override
    def update(self):
        self._emit_points_changed()
        super().update()

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

    # ---- mouse helpers ------------------------------------------------------
    def _dist2(self, a: QtCore.QPointF, b: QtCore.QPointF) -> float:
        dx = float(a.x() - b.x())
        dy = float(a.y() - b.y())
        return dx * dx + dy * dy

    def _index_at(self, pos: QtCore.QPointF) -> int | None:
        r2 = self._hit_radius ** 2
        for i, p in enumerate(self._path.points):
            if self._dist2(point_to_qpoint(p), pos) <= r2:
                return i
        return None

    def _constrain_to_gradient(self, pos: QtCore.QPointF) -> QtCore.QPointF | None:
        return pos if self._gradient.contains_point(pos) else None

    # ---- mouse events -------------------------------------------------------
    def _can_close_now(self) -> bool:
        return (not self._path.closed) and (len(self._path.points) >= 3)

    def mousePressEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        pos = QtCore.QPointF(e.position())
        idx = self._index_at(pos)

        # --- close on clicking the first point ---------------------------------
        if (
                e.button() == QtCore.Qt.MouseButton.LeftButton
                and idx == 0
                and self._can_close_now()
        ):
            self._path.closed = True
            self._drag_index = None
            self.update()
            return
        # -----------------------------------------------------------------------

        is_remove = (
                e.button() == QtCore.Qt.MouseButton.RightButton
                or (
                    e.button() == QtCore.Qt.MouseButton.LeftButton
                    and e.modifiers() & QtCore.Qt.KeyboardModifier.ControlModifier
                )
        )

        if is_remove and idx is not None:
            self._path = self._path.remove_point(idx)
            self._drag_index = None
            self.update()
            return

        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            if idx is not None:
                self._drag_index = idx
            else:
                inside = self._constrain_to_gradient(pos)
                if inside is not None:
                    # remember old state to recover the inserted index
                    old_closed = self._path.closed
                    old_len = len(self._path.points)
                    new_pt = (inside.x(), inside.y())

                    self._path = self._path.add_point(new_pt)

                    # if open: append => last index; if closed: find actual inserted slot
                    if old_closed and len(self._path.points) == old_len + 1:
                        try:
                            self._drag_index = self._path.points.index(new_pt)
                        except ValueError:
                            self._drag_index = len(self._path.points) - 1
                    else:
                        self._drag_index = len(self._path.points) - 1

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
            self._path = self._path.edit_point(self._drag_index, (inside.x(), inside.y()))
            self.update()

    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        if not self._active:
            return
        if e.button() == QtCore.Qt.MouseButton.LeftButton:
            self._drag_index = None

    # ---- painting -----------------------------------------------------------
    def _make_path(self) -> QtGui.QPainterPath:
        pts = self._path.points
        closed = self._path.closed
        ops = self._path.editor.path_ops(pts, closed)
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

    def paintEvent(self, _):
        if not self._path.points:
            return
        p = QtGui.QPainter(self)
        p.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)
        if not self._active:
            p.setOpacity(0.5)

        path = self._make_path()
        pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 160), 2.0)
        p.setPen(pen)
        p.drawPath(path)

        # optional control lines
        if len(self._path.points) >= 2:
            p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 60), 1.0, QtCore.Qt.PenStyle.DashLine))
            for i in range(len(self._path.points) - 1):
                p.drawLine(
                    point_to_qpoint(self._path.points[i]),
                    point_to_qpoint(self._path.points[i + 1])
                )
            if self._path.closed:
                p.drawLine(
                    point_to_qpoint(self._path.points[-1]),
                    point_to_qpoint(self._path.points[0])
                )
        p.setBrush(QtGui.QColor(255, 255, 255, 230))
        p.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0, 200), 1.0))
        r = self._hit_radius
        for pt in self._path.points:
            p.drawEllipse(QtCore.QRectF(pt[0] - r * 0.5, pt[1] - r * 0.5, r, r))

        p.end()

    # ---- signals ------------------------------------------------------------
    def _emit_points_changed(self):
        self.pointsChanged.emit()
