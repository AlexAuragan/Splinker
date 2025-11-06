from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core import Palette, Gradient


class GradientDisplayComponent(QtWidgets.QWidget):
    """
    Qt widget that directly renders/edits the active Layer of a Palette.
    No per-layer Qt widgets; pure view/controller bound to a pure-Python model.
    """

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)
        self._palette = palette

        # gradient cache
        self._bg = QtGui.QImage()
        self._bg_dpr: Optional[float] = None

        self.setAttribute(QtCore.Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

        if palette is not None:
            self.set_palette(palette)


    @property
    def bg(self):
        return self._bg

    # ---------- binding ----------
    def set_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._invalidate_background()
        self.update()

    def clear_palette(self) -> None:
        self._palette = None
        self._invalidate_background()
        self.update()

    def _invalidate_background(self):
        self._bg = QtGui.QImage()
        self._bg_dpr = None

    # ---------- size hints ----------
    def sizeHint(self):
        return QtCore.QSize(600, 600)

    def minimumSizeHint(self):
        return QtCore.QSize(200, 200)

    # ---------- gradient cache/render ----------
    def ensure_bg_current(self):
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

        lyr = self._palette.active_layer
        grad: Optional[Gradient] = None if lyr is None else lyr.gradient
        if grad is not None:
            inv_dpr = 1.0 / dpr
            for y in range(h):
                wy = (y + 0.5) * inv_dpr
                for x in range(w):
                    wx = (x + 0.5) * inv_dpr
                    color = grad.color_at(wx, wy)
                    if color is None:
                        continue
                    qcol = color.to_QColor()
                    if qcol is not None:
                        img.setPixelColor(x, y, qcol)

        self._bg = img
        self._bg_dpr = dpr

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


    def paint_event(self, painter, event):
        self.ensure_bg_current()
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(0, 0, self.bg)