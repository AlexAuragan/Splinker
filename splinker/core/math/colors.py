from typing import TYPE_CHECKING

from splinker.core.math.utils import rgb_to_hsv_255

if TYPE_CHECKING:
    from PySide6.QtGui import QColor

class Color:
    """
    Pure-theory color container
    """

    def __init__(
            self, /,
            h: int = None,
            s: int = None,
            v: int = None,
            r: int = None,
            g: int = None,
            b: int = None,
            a: int = 255
    ):
        if not any(arg is None for arg in (h, s, v, r, g, b)):
            raise ValueError("Please set the colors via RGB(a) or HSV(a).")
        if any(arg is not None for arg in (h, s, v)) and any(arg is not None for arg in (r, g, b)):
            raise ValueError("Only set the color via RGB(a) or HSV(a).")
        if any(arg is not None for arg in (h, s, v)) and any(arg is None for arg in (h, s, v)):
            raise ValueError("Please set all 3 colors h, s and v.")
        if any(arg is not None for arg in (r, g, b)) and any(arg is None for arg in (r, g, b)):
            raise ValueError("Please set all 3 colors r, g and b.")
        self.h: int = h
        self.s: int = s
        self.v: int = v
        self.a: int = a
        if any(arg is not None for arg in (r, g, b)):
            h, s, v = rgb_to_hsv_255(r, g, b)
            self.h = h
            self.s = s
            self.v = v

    @staticmethod
    def from_hsv(h: int, s: int, v: int, a: int = 255):
        return Color(h=h, s=s, v=v, a=a)

    @staticmethod
    def from_rgb(r: int, g: int, b: int, a: int = 255):
        h, s, v = rgb_to_hsv_255(r, g, b)
        return Color(h=h, s=s, v=v, a=a)

    def to_hsva(self, /) -> tuple[int, int, int, int]:
        return self.h, self.s, self.v, self.a

    def to_QColor(self) -> "QColor":
        from PySide6.QtGui import QColor
        r, g, b = self.to_rgb()
        return QColor(r, g, b)

    @staticmethod
    def from_qcolor(qcolor: "QColor") -> "Color":
        return Color(h=qcolor.hue(), s=qcolor.saturation(), v=qcolor.value(), a=qcolor.alpha())

    def isValid(self):
        return True

    def to_rgb(self) -> tuple[int, int, int]:
        if self.h == -1:
            r = g = b = self.v
            return r, g, b

        h = self.h / 60.0
        s = self.s / 255.0
        v = self.v / 255.0

        i = int(h) % 6
        f = h - i
        p = v * (1 - s)
        q = v * (1 - f * s)
        t = v * (1 - (1 - f) * s)

        if i == 0:
            r, g, b = v, t, p
        elif i == 1:
            r, g, b = q, v, p
        elif i == 2:
            r, g, b = p, v, t
        elif i == 3:
            r, g, b = p, q, v
        elif i == 4:
            r, g, b = t, p, v
        else:  # i == 5
            r, g, b = v, p, q

        return int(r * 255), int(g * 255), int(b * 255)