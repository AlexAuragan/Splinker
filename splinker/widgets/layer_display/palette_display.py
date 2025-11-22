from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core import Palette, Layer
from splinker.widgets.layer_display.distribution_editor import DistributionEditorDisplayComponent
from splinker.widgets.layer_display.gradient_display import GradientDisplayComponent
from splinker.widgets.layer_display.path_editor import PathEditorDisplayComponent


class PaletteDisplayComponent(QtWidgets.QWidget):
    """
    Qt widget that directly renders/edits the active Layer of a Palette.
    No per-layer Qt widgets; pure view/controller bound to a pure-Python model.
    """
    pointsChanged = QtCore.Signal()
    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette= palette
        self._drag_index: Optional[int] = None
        self._hit_radius = 10.0
        self._active = True

        # gradient cache
        self.gradient_dc = GradientDisplayComponent(self._palette, self)
        self.path_editor_dc = PathEditorDisplayComponent(self._palette, self)
        self.distribution_editor_dc = DistributionEditorDisplayComponent(self._palette, self)

        self.path_editor_dc.pointsChanged.connect(self.pointsChanged.emit)
        self.distribution_editor_dc.pointsChanged.connect(self.pointsChanged.emit)

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        if palette is not None:
            self.set_palette(palette)

    # ---------- binding ----------
    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.gradient_dc.set_palette(palette)
        self.path_editor_dc.set_palette(palette)
        self.distribution_editor_dc.set_palette(palette)
        self.update()

    def clear_palette(self) -> None:
        self._palette = None
        self.gradient_dc.clear_palette()
        self.path_editor_dc.clear_palette()
        self.distribution_editor_dc.clear_palette()
        self.update()

    # ---------- helpers ----------
    def _layer(self) -> Optional[Layer]:
        if self._palette is None:
            return None
        if self._palette.active_idx < 0 or self._palette.active_idx >= len(self._palette):
            return None
        return self._palette.active_layer


    # ---------- size hints ----------
    def sizeHint(self):
        return self.gradient_dc.sizeHint()

    def minimumSizeHint(self):
        return self.gradient_dc.minimumSizeHint()

    # ---------- Qt events ----------
    def mousePressEvent(self, e: QtGui.QMouseEvent):
        self.path_editor_dc.mouse_press_event(e)
        self.distribution_editor_dc.mouse_press_event(e)

    def mouseMoveEvent(self, e: QtGui.QMouseEvent):
        self.path_editor_dc.mouse_move_event(e)
        self.distribution_editor_dc.mouse_move_event(e)


    def mouseReleaseEvent(self, e: QtGui.QMouseEvent):
        self.path_editor_dc.mouse_release_event(e)
        self.distribution_editor_dc.mouse_release_event(e)


    # ---------- painting ----------
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing, True)

        self.gradient_dc.paint_event(painter, event)
        self.path_editor_dc.paint_event(painter, event)
        self.distribution_editor_dc.paint_event(painter, event)


    # ---------- API for Canvas ----------
    def notify_active_layer_changed(self):
        """
        Called by the Canvas when the Palette.active_idx changes.
        We just invalidate caches and repaint.
        """
        self.gradient_dc.notify_active_layer_changed()
        self.path_editor_dc.notify_active_layer_changed()
        self.distribution_editor_dc.notify_active_layer_changed()
        self.update()

    def notify_gradient_changed(self) -> None:
        """
        Call this when the active layer's gradient object changes.
        Forces the background cache to rebuild and repaints.
        """
        self.gradient_dc.notify_gradient_changed()
        self.update()

