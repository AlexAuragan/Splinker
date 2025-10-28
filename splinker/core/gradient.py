import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass(frozen=True)
class HSVa:
    """
    Pure-theory color container (HSV + alpha), using the same integer ranges
    as Qt for easy bridging:
      - h: 0..359, or -1 if undefined (achromatic)
      - s, v, a: 0..255
    """
    h: int   # 0..359, or -1
    s: int   # 0..255
    v: int   # 0..255
    a: int   # 0..255

    def get_hsva(self, /) -> Tuple[int, int, int, int]:
        return self.h, self.s, self.v, self.a


class Gradient2D(ABC):
    """
    Pure theoretical 2D gradient: operates in an arbitrary continuous
    coordinate space (no pixels or frameworks involved).

    Required queries:
      - contains_point(x, y): whether (x, y) is within the gradient support
      - color_at(x, y): return HSVa at (x, y), or None if outside/undefined
      - point_for_color(color): inverse mapping for colors that exist on the gradient,
        returning (x, y) or None if not representable.
    """

    @abstractmethod
    def contains_point(self, x: float, y: float, /) -> bool:
        pass

    @abstractmethod
    def color_at(self, x: float, y: float, /) -> Optional[HSVa]:
        pass

    @abstractmethod
    def point_for_color(self, color: HSVa, /) -> Optional[Tuple[float, float]]:
        pass


class HsvWheelGradient(Gradient2D):
    """
    Hue-Saturation wheel (Value fixed), centered at (cx, cy) with radius R.

    Mapping:
      - hue = angle(theta) in degrees, [0, 360) where 0° is +X axis, CCW positive
      - saturation = radial distance / R, clamped to [0, 1]
      - value = fixed (0..255), alpha = fixed (0..255)

    Only colors with the configured 'value' and 'alpha' exist on this gradient.
    Colors with s==0 map to the center. Achromatic hue (h==-1) is accepted:
    we pick angle = 0° by convention for the inverse (center if s==0).
    """

    def __init__(self, cx: float, cy: float, radius: float, /, *, value: int = 255, alpha: int = 255):
        self.cx = float(cx)
        self.cy = float(cy)
        self.R = float(radius)
        self.value = int(max(0, min(255, value)))
        self.alpha = int(max(0, min(255, alpha)))

    # --- Geometry helpers

    def contains_point(self, x: float, y: float, /) -> bool:
        dx = x - self.cx
        dy = y - self.cy
        return (dx * dx + dy * dy) <= (self.R * self.R)

    # --- Forward mapping: (x, y) -> HSVa

    def color_at(self, x: float, y: float, /) -> Optional[HSVa]:
        if self.R <= 0.0:
            return None
        dx = x - self.cx
        dy = y - self.cy
        r = math.hypot(dx, dy)
        if r > self.R:
            return None

        # hue in [0, 360), atan2 returns [-pi, pi]
        ang_deg = math.degrees(math.atan2(dy, dx))
        hue = int((ang_deg + 360.0) % 360.0)

        # saturation in [0..255]
        sat = int(round(255.0 * (r / self.R)))
        sat = max(0, min(255, sat))

        return HSVa(h=hue, s=sat, v=self.value, a=self.alpha)

    # --- Inverse mapping: HSVa -> (x, y)

    def point_for_color(self, color: HSVa, /) -> Optional[Tuple[float, float]]:
        if self.R <= 0.0:
            return None

        h, s, v, a = color.get_hsva()

        # Only colors that lie on this wheel (fixed V and A) are representable
        if v != self.value or a != self.alpha:
            return None

        # s must be within [0..255]
        if s < 0 or s > 255:
            return None

        # Compute radius from saturation
        r = (s / 255.0) * self.R

        # Determine angle. If hue is undefined (achromatic), pick 0° by convention.
        if h is None or h < 0:
            angle_rad = 0.0
        else:
            angle_rad = math.radians(float(h) % 360.0)

        x = self.cx + r * math.cos(angle_rad)
        y = self.cy + r * math.sin(angle_rad)

        # By construction, point is inside (or on) the wheel for s∈[0,255]
        # Still, we enforce geometry consistency:
        return (x, y) if self.contains_point(x, y) else None
