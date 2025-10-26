import math
from PySide6 import QtCore, QtGui, QtWidgets
from abc import ABC, abstractmethod

from widgets.utils import ABCQtMeta


class GradientWidget(QtWidgets.QWidget, ABC, metaclass=ABCQtMeta):
    def __init__(self):
        super().__init__()

        self.setMouseTracking(True)

        self._bg = QtGui.QImage() # Cached background
        self._bg_dpr: float | None = None

        self._pad = 2

    @property
    def pad(self):
        return self._pad

    def sizeHint(self, /):
        return QtCore.QSize(600, 600)

    def minimumSize(self, /):
        return QtCore.QSize(200, 200)

    @abstractmethod
    def render_background(self):
        pass

    @abstractmethod
    def point_for_color(self, color: QtGui.QColor, /):
        pass

    @abstractmethod
    def contains_point(self, pt: QtCore.QPointF, /) -> bool:
        """
        Return True if the given widget-space point lies within the gradient area.
        Implementations must ignore device pixel ratio and operate in widget coordinates.
        """
        pass

    def paintEvent(self, event):
        """
        Makes a gradient circle that shows all the colors a monitor can display
        (HSV color wheel: hue by angle, saturation by distance, value fixed).
        :param event:
        :return:
        """
        # Rebuild cache if size or DPR changed, or cache is empty
        if self._bg.isNull() or self._bg.width() != int(self.width() * self.devicePixelRatioF()) \
                or self._bg.height() != int(self.height() * self.devicePixelRatioF()) \
                or self._bg_dpr != self.devicePixelRatioF():
            self.render_background()

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.SmoothPixmapTransform, True)
        painter.drawImage(0, 0, self._bg)
        painter.end()

    def _ensure_bg_current(self, /):
        """
        Ensure the cached background image matches current size/DPR.
        Safe to call from non-paint paths before sampling.
        """
        dpr = self.devicePixelRatioF()
        if self._bg.isNull() \
                or self._bg.width() != int(self.width() * dpr) \
                or self._bg.height() != int(self.height() * dpr) \
                or self._bg_dpr != dpr:
            self.render_background()

    def color_at(self, pt: QtCore.QPointF, /) -> QtGui.QColor | None:
        """
        Sample the rendered gradient at a widget-space point.
        Returns a QColor or None if out of bounds or background not available.
        NOTE: Does not check self.contains_point(pt); caller decides validity.
        """
        self._ensure_bg_current()
        if self._bg.isNull():
            return None
        dpr = self.devicePixelRatioF()
        x = int(float(pt.x()) * dpr)
        y = int(float(pt.y()) * dpr)
        if x < 0 or y < 0 or x >= self._bg.width() or y >= self._bg.height():
            return None
        # QImage.pixel -> QRgb (int). Convert to QColor.
        return QtGui.QColor.fromRgba(self._bg.pixel(x, y))

    def colors_for_points(self, pts: list[QtCore.QPointF], /) -> list[QtGui.QColor | None]:
        """
        Convenience: sample a list of points (widget coords).
        """
        self._ensure_bg_current()
        out: list[QtGui.QColor | None] = []
        for p in pts:
            out.append(self.color_at(p))
        return out

class GradientCircleWidget(GradientWidget):
    def render_background(self):
        # Create a hi-DPI aware image for crisp rendering on scaled displays
        dpr = self.devicePixelRatioF()
        w = max(1, int(self.width() * dpr))
        h = max(1, int(self.height() * dpr))

        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)  # fully transparent

        # Circle geometry
        cx = (w - 1) * 0.5
        cy = (h - 1) * 0.5
        radius = max(0.0, min(w, h) * 0.5 - self.pad * dpr)

        # Per-pixel HSV wheel (H: angle, S: radius, V: 255)
        # Note: iterate rows then columns for cache locality
        for y in range(h):
            dy = y - cy
            for x in range(w):
                dx = x - cx
                r = math.hypot(dx, dy)
                if r <= radius:
                    # atan2 returns [-pi, pi]; map to [0, 360)
                    ang = math.degrees(math.atan2(dy, dx))
                    hue = int((ang + 360.0) % 360.0)
                    sat = int(255.0 * (r / radius))
                    col = QtGui.QColor()
                    col.setHsv(hue, sat, 255, 255)
                    img.setPixelColor(x, y, col)
                # else leave fully transparent
        self._bg = img
        self._bg_dpr = dpr

    def contains_point(self, pt: QtCore.QPointF, /) -> bool:
        """
        Widget-space hit-test that mirrors the render geometry:
        inside circle of radius (min(width, height)/2 - pad), centered in the widget.
        """
        w = self.width()
        h = self.height()
        if w <= 0 or h <= 0:
            return False

        cx = (w - 1) * 0.5
        cy = (h - 1) * 0.5
        radius = max(0.0, min(w, h) * 0.5 - self.pad)

        dx = float(pt.x()) - cx
        dy = float(pt.y()) - cy
        return (dx * dx + dy * dy) <= (radius * radius)

    def point_for_color(self, color: QtGui.QColor, /) -> QtCore.QPointF | None:
        """
        Map a QColor to a widget-space point on the HSV wheel:
        hue -> angle, saturation -> radius (value is ignored; wheel renders V=255).
        """
        # HSV ints: h in [0..359] or -1 if undefined (achromatic), s,v in [0..255]
        h, s, v, a = color.getHsv()
        if h < 0:
            h = 0  # achromatic: pick an arbitrary angle; radius from s will be 0 anyway if s==0

        w = self.width()
        hgt = self.height()
        if w <= 0 or hgt <= 0:
            return None

        cx = (w - 1) * 0.5
        cy = (hgt - 1) * 0.5
        radius = max(0.0, min(w, hgt) * 0.5 - self.pad)

        r = float(s) / 255.0 * radius
        ang = math.radians(float(h))

        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        pt = QtCore.QPointF(x, y)

        return pt if self.contains_point(pt) else None