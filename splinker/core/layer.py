from dataclasses import dataclass, field

from . import HSVa
from .gradients import Gradient, HsvWheelGradient
from .path import Path


@dataclass
class Layer:
    gradient: Gradient = field(default_factory=HsvWheelGradient)
    path: Path = field(default_factory=Path)
    name: str = "Overlay"

    def sample(self, n=64):
        """
        Returns (stops: list[(pos:float, QColor)], has_data: bool).
        Uses the active path editor's interpolate() to sample the path and
        colors the samples via the gradient widget.
        """

        points = self.path.points
        if not points:
            return []

        # 1) sample along the *actual path* (editor-aware)
        #    keep it modest to avoid hundreds of stops in a tiny bar
        samples = self.path.editor.interpolate(points, self.path.closed, n=n)
        if not samples or len(samples) < 2:
            return [], False

        # 2) color the samples with the current gradient widget
        cols = self.gradient.points_to_colors(samples)
        if not cols or len(cols) != len(samples):
            return [], False

        # 3) build gradient stops (uniform by sample index -> [0..1])
        stops: list[tuple[float, HSVa | None]] = []
        N = len(samples)
        for i in range(N):
            c = cols[i]
            t = i / (N - 1)
            stops.append((t, c))

        # make sure we have at least 2 valid stops
        if len(stops) < 2:
            return [], False

        # clamp/sort just in case (Qt expects non-decreasing positions)
        stops.sort(key=lambda t: t[0])
        return stops, True
