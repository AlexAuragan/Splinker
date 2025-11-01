from PySide6 import QtCore, QtGui, QtWidgets

from splinker.core import Point
from splinker.core.gradients import Gradient

class GradientOverlayWidget(QtWidgets.QWidget):
    def __init__(self, gradient: Gradient):
        super().__init__()

        self.setMouseTracking(True)

        self._bg = QtGui.QImage()
        self._bg_dpr: float | None = None

        self._pad = 2
        self._gradient = gradient

    @property
    def pad(self):
        return self._pad

    @property
    def gradient(self):
        return self._gradient

    def set_gradient(self, gradient, /):
        """
        Inject/replace the underlying pure gradient. The gradient is expected to implement:
          - contains_point(x: float, y: float) -> bool
          - color_at(x: float, y: float) -> color-like or None
          - point_for_color(color_like) -> (x, y) or None
        """
        self._gradient = gradient
        # Invalidate cache & repaint
        self._bg = QtGui.QImage()
        self._bg_dpr = None
        self.update()

    def sizeHint(self, /):
        return QtCore.QSize(600, 600)

    def minimumSize(self, /):
        return QtCore.QSize(200, 200)

    # ------------------------
    # Dependency-driven ops
    # ------------------------

    def render_background(self):
        """
        Generic renderer: samples the injected gradient in widget-space.
        If no gradient is set, produces a transparent image.
        """
        dpr = self.devicePixelRatioF()
        w = max(1, int(self.width() * dpr))
        h = max(1, int(self.height() * dpr))

        img = QtGui.QImage(w, h, QtGui.QImage.Format.Format_ARGB32_Premultiplied)
        img.setDevicePixelRatio(dpr)
        img.fill(0)  # fully transparent

        grad = self._gradient
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

    def contains_point(self, pt: QtCore.QPointF, /) -> bool:
        """
        Delegate to the injected gradient (widget-space).
        """
        grad = self._gradient
        if grad is None:
            return False
        return bool(grad.contains_point(float(pt.x()), float(pt.y())))

    def point_for_color(self, color: QtGui.QColor, /):
        """
        Delegate to the injected gradient. Accepts a QColor and adapts it to the
        theoretical gradient’s expected input (HSVa-like).
        """
        grad = self._gradient
        if grad is None:
            return None

        # Adapt QColor -> object with .get_hsva()
        h, s, v, a = color.getHsv()
        adapter = self._HSVaAdapter(h, s, v, a)
        pt = grad.point_for_color(adapter)
        if pt is None:
            return None
        x, y = pt
        qpt = QtCore.QPointF(float(x), float(y))
        return qpt if self.contains_point(qpt) else None

    # ------------------------
    # Existing rendering/cache
    # ------------------------

    def paintEvent(self, event):
        """
        Draw the cached background. Rebuild if size/DPR changed.
        """
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
        Sample the *rendered* gradient at a widget-space point.
        (Keeps your cached-image sampling, independent of the injected gradient.)
        """
        self._ensure_bg_current()
        if self._bg.isNull():
            return None
        dpr = self.devicePixelRatioF()
        x = int(float(pt.x()) * dpr)
        y = int(float(pt.y()) * dpr)
        if x < 0 or y < 0 or x >= self._bg.width() or y >= self._bg.height():
            return None
        return QtGui.QColor.fromRgba(self._bg.pixel(x, y))

    def colors_for_points(self, pts: list[QtCore.QPointF | Point], /) -> list[QtGui.QColor | None]:
        """
        Convenience: sample a list of points (widget coords).
        """
        self._ensure_bg_current()
        out: list[QtGui.QColor | None] = []
        for p in pts:
            if not isinstance(p, QtCore.QPointF):
                p = QtCore.QPointF(p[0], p[1])
            out.append(self.color_at(p))
        return out

    # ------------------------
    # Small adapters/helpers
    # ------------------------

    class _HSVaAdapter:
        """
        Minimal adapter to satisfy gradients expecting an object with .get_hsva().
        """
        def __init__(self, h, s, v, a):
            self._hsva = (int(h), int(s), int(v), int(a))
        def get_hsva(self):
            return self._hsva

    def _to_qcolor(self, col_like):
        """
        Accepts:
          - QtGui.QColor -> return as-is
          - object with .get_hsva() -> convert via QColor.fromHsv
          - 4-tuple (h, s, v, a) -> convert via QColor.fromHsv
          - None -> None
        """
        if col_like is None:
            return None
        if isinstance(col_like, QtGui.QColor):
            return col_like
        get = getattr(col_like, "get_hsva", None)
        if callable(get):
            h, s, v, a = get()
            return QtGui.QColor.fromHsv(int(h), int(s), int(v), int(a))
        if isinstance(col_like, tuple) and len(col_like) == 4:
            h, s, v, a = col_like
            return QtGui.QColor.fromHsv(int(h), int(s), int(v), int(a))
        # Fallback: unsupported type
        return None
