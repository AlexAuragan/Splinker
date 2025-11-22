from dataclasses import dataclass, field
from typing import Sequence, TYPE_CHECKING

from . import project_point_to_segment, dist2
from .point_editors import PointEditorComponent, CatmullRomSplinePE
from .registries import point_editor_registry
from splinker.core.math import Point

if TYPE_CHECKING:
    from PySide6 import QtGui


@dataclass()
class Path:
    """
      - points: control polygon vertices
      - closed: whether the path is closed
      - spline: strategy to convert points -> cubic segments/ops
      - params: future-proof bag for per-path settings (kept opaque here)
    """
    points: list[Point] = field(default_factory=list)
    closed: bool = False
    _editor: PointEditorComponent = field(default_factory=CatmullRomSplinePE)
    params: dict[str, float] = field(default_factory=dict)


    def clear(self):
        self.points = []
        self.closed = False
        self.params = {}

    # read-only views
    def as_point(self) -> Sequence[Point]:
        return tuple(self.points)

    def interpolate(self, n=200):
        return self._editor.interpolate(self.points,self.closed,n)

    def closest_point(self, point: Point) -> Point:
        """
        Return the closest point on the interpolated path to the given point.

        The interpolation is sampled densely (200 points) and the shortest
        projection to the resulting polyline is returned. If the path has no
        points, the input is returned unchanged.
        """
        samples = self._editor.interpolate(self.points, self.closed, n=200)
        if not samples:
            return point

        best_point = samples[0]
        best_d2 = dist2(point, best_point)

        for a, b in zip(samples, samples[1:]):
            candidate, d2 = project_point_to_segment(point, a, b)
            if d2 < best_d2:
                best_point = candidate
                best_d2 = d2

        if self.closed and len(samples) > 1 and samples[-1] != samples[0]:
            candidate, d2 = project_point_to_segment(point, samples[-1], samples[0])
            if d2 < best_d2:
                best_point = candidate

        return best_point

    def segments(self) -> Sequence[tuple[Point, Point, Point]]:
        return tuple(self._editor.segments(self.points, self.closed))

    def add_point(self, p: Point) -> "Path":
        self.points = self._editor.add_point(self.points, p, self.closed)
        self.closed = (self.closed and len(self.points) >= 3)
        return self


    def remove_point(self, index: int) -> "Path":
        self.points = self._editor.remove_point(self.points, index)
        self.closed = self.closed if len(self.points) >= 3 else False
        return self

    def edit_point(self, index: int, p: Point) -> "Path":
        self.points = self._editor.edit_point(self.points, index, p)
        return self


    def set_point_editor(self, new_editor: PointEditorComponent) -> "Path":
        """
        Convert current path into new editor's control points:
        - Sample 100 points using current editor.
        - Fit new editor control points from that sample.
        - Keep 'closed' if the new editor supports it; circles force closed.
        """
        # sample with current editor
        sample = self._editor.interpolate(self.points, self.closed, n=100)
        # fit target controls
        new_points = new_editor.fit_from_sample(sample, self.closed)
        self._editor = new_editor
        self.points = new_points
        self.closed = new_editor.default_closed or (self.closed if len(new_points) >= 3 else False)
        return self


    # ---- serialization -------------------------------------------------------
    def to_dict(self) -> dict:
        """
        Serialize without relying on reflection. If spline_name is None,
        attempt to pick the first matching registry key by isinstance.
        """
        return {
            "points": list(self.points),
            "closed": bool(self.closed),
            "params": dict(self.params),
            "editor": {v:k for k,v in point_editor_registry.items()}.get(type(self._editor))
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Path":
        pts: list[Point] = [tuple(map(float, p)) for p in data["points"]]
        closed = data["closed"]
        editor = point_editor_registry[data["editor"]]()
        params = dict(data.get("params", {}))
        return cls(points=pts, closed=closed, _editor=editor, params=params)

    def make_qpath(self) -> "QtGui.QPainterPath":
        from PySide6 import QtCore, QtGui
        pts = self.points
        closed = self.closed
        ops = self._editor.path_ops(pts, closed)

        qp = QtGui.QPainterPath()
        qpf = lambda t: QtCore.QPointF(t[0], t[1])

        for op, data in ops:
            if op == "M":
                qp.moveTo(qpf(data))
            elif op == "L":
                qp.lineTo(qpf(data))
            elif op == "C":
                c1, c2, p2 = data
                qp.cubicTo(qpf(c1), qpf(c2), qpf(p2))
            elif op == "Z":
                qp.closeSubpath()
        return qp