import math
from abc import ABC, abstractmethod
from typing import Optional, Tuple

from .math import HSVa, Point
from .registries import register_gradient

class Gradient(ABC):
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
    def point_at(self, color: HSVa, /) -> Optional[Tuple[float, float]]:
        pass

    def colors_to_point(self, colors: list[HSVa]):
        return [self.point_at(color) for color in colors]

    def points_to_colors(self, points: list[Point]):
        return [self.color_at(point[0], point[1]) for point in points]

@register_gradient("HSV Wheel")
class HsvWheelGradient(Gradient):
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

    def __init__(self, cx: float = 300, cy: float = 300, radius: float = 298, /, *, value: int = 255, alpha: int = 255):
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

    def point_at(self, color: HSVa, /) -> Optional[Tuple[float, float]]:
        if self.R <= 0.0:
            return None

        h, s, v, a = color.to_hsva()

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

@register_gradient("HSV Square")
class HsvSquareGradient(Gradient):
    """
    HSV square for a given hue:
      - X axis: value/brightness (black → white/color)
      - Y axis: saturation (white → pure color)
      - hue: fixed
      - alpha: fixed

    The square is centered at (cx, cy) with side length S.
    HSV ranges:
      - hue: fixed (0..359)
      - saturation: 0..255 (top→bottom)
      - value: 0..255 (left→right)
      - alpha: fixed
    """

    def __init__(self, cx: float = 300, cy: float = 300, size: float = 298, /, *, hue: int = 0, alpha: int = 255):
        self.cx = float(cx)
        self.cy = float(cy)
        self.S = float(size)
        self.hue = int(max(-1, min(359, hue)))
        self.alpha = int(max(0, min(255, alpha)))

        # precompute geometry
        half = self.S * 0.5
        self.x0 = self.cx - half
        self.y0 = self.cy - half
        self.x1 = self.cx + half
        self.y1 = self.cy + half

    # --- geometry check
    def contains_point(self, x: float, y: float, /) -> bool:
        if self.S <= 0.0:
            return False
        return (self.x0 <= x <= self.x1) and (self.y0 <= y <= self.y1)

    # --- forward: (x, y) -> HSVa
    def color_at(self, x: float, y: float, /) -> Optional[HSVa]:
        if self.S <= 0.0 or not self.contains_point(x, y):
            return None

        # horizontal: value 0..255 (black→white)
        tx = (x - self.x0) / self.S
        # vertical: saturation 0..255 (top→bottom)
        ty = (y - self.y0) / self.S

        s = int(round(max(0.0, min(1.0, ty)) * 255.0))
        v = int(round(max(0.0, min(1.0, tx)) * 255.0))

        return HSVa(h=self.hue, s=s, v=v, a=self.alpha)

    # --- inverse: HSVa -> (x, y)
    def point_at(self, color: HSVa, /) -> Optional[Tuple[float, float]]:
        if self.S <= 0.0:
            return None

        h, s, v, a = color.to_hsva()

        if h != self.hue or a != self.alpha:
            return None
        if s < 0 or s > 255 or v < 0 or v > 255:
            return None

        tx = v / 255.0
        ty = s / 255.0

        x = self.x0 + tx * self.S
        y = self.y0 + ty * self.S

        return (x, y) if self.contains_point(x, y) else None
