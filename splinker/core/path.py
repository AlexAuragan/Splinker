from dataclasses import dataclass, field
from typing import Sequence

from .point_editors import PointEditorComponent, CatmullRomSplinePE
from .registries import point_editor_registry
from splinker.core.math import Point

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
    editor: PointEditorComponent = field(default_factory=CatmullRomSplinePE)
    params: dict[str, float] = field(default_factory=dict)


    def clear(self):
        self.points = []
        self.closed = False
        self.params = {}

    # read-only views
    def as_point(self) -> Sequence[Point]:
        return tuple(self.points)

    def segments(self) -> Sequence[tuple[Point, Point, Point]]:
        return tuple(self.editor.segments(self.points, self.closed))

    def add_point(self, p: Point) -> "Path":
        self.points = self.editor.add_point(self.points, p, self.closed)
        self.closed = (self.closed and len(self.points) >= 3)
        return self


    def remove_point(self, index: int) -> "Path":
        self.points = self.editor.remove_point(self.points, index)
        self.closed = self.closed if len(self.points) >= 3 else False
        return self

    def edit_point(self, index: int, p: Point) -> "Path":
        self.points = self.editor.edit_point(self.points, index, p)
        return self


    def set_point_editor(self, new_editor: PointEditorComponent) -> "Path":
        """
        Convert current path into new editor's control points:
        - Sample 100 points using current editor.
        - Fit new editor control points from that sample.
        - Keep 'closed' if the new editor supports it; circles force closed.
        """
        # sample with current editor
        sample = self.editor.interpolate(self.points, self.closed, n=100)
        # fit target controls
        new_points = new_editor.fit_from_sample(sample, self.closed)
        self.editor = new_editor
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
            "editor": {v:k for k,v in point_editor_registry.items()}.get(type(self.editor))
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Path":
        pts = [tuple(map(float, p)) for p in data["points"]]
        closed = data["closed"]
        editor = point_editor_registry[data["editor"]]()
        params = dict(data.get("params", {}))
        return cls(points=pts, closed=closed, editor=editor, params=params)