from abc import ABC, abstractmethod
from typing import override

from .math import Point, best_edge_index_for_insertion, Op, sample_cubic_path

from .registries import register_point_editor


class PointEditorComponent(ABC):
    max_number_points: int | None = None
    default_closed = False

    @abstractmethod
    def add_point(self, path_points: list[Point], new_point: Point, closed: bool) -> list[Point]:
        """
        Insert the new point in the appropriate place (may insert multiple points if the figure
        requires a minimum cardinality, e.g., circle center+radius).
        """

    @abstractmethod
    def remove_point(self, path_points: list[Point], idx: int) -> list[Point]:
        """
        Remove the selected point (may remove multiple if needed to preserve figure invariants).
        """

    @abstractmethod
    def edit_point(self, path_points: list[Point], idx: int, edited_point: Point) -> list[Point]:
        """
        Move a selected point; implementations may move other points to respect constraints.
        """

    @abstractmethod
    def segments(self, pts: list[Point], closed: bool, /) -> list[tuple[Point, Point, Point]]:
        """
        Yield (c1, c2, p2) for each cubic segment, assuming a moveTo at pts[0].
        """

    def path_ops(self, pts: list[Point], closed: bool, /) -> list[Op]:
        """
        Convert control points to simple drawing ops:
          - ("M", (x,y))       moveTo
          - ("L", (x,y))       lineTo (only for open 2-point cases)
          - ("C", (c1,c2,p2))  cubicTo
          - ("Z", ())          closePath
        """
        n = len(pts)
        if n == 0:
            return []
        ops: list[Op] = [("M", pts[0])]
        if n == 1:
            return ops
        if n == 2 and not closed:
            ops.append(("L", pts[1]))
            return ops
        for c1, c2, p2 in self.segments(pts, closed):
            ops.append(("C", (c1, c2, p2)))
        if closed:
            ops.append(("Z", ()))
        return ops

    @abstractmethod
    def fit_from_sample(self, sample: list[Point], closed: bool) -> list[Point]:
        """
        Return control points for this editor that best-approximate the given sample polyline.
        Coarse is fine (e.g., downsample for splines; mean circle fit for circles).
        """

    @abstractmethod
    def interpolate(self, pts: list[Point], closed: bool, n=100) -> list[Point]:
        """
        Return n points sampled along the path defined by pts/closed for this editor.
        """


@register_point_editor("catmull-rom")
class CatmullRomSplinePE(PointEditorComponent):
    """
    Freeform editor for Catmull-Rom-like paths:
      - add: insert after the nearest segment by projection (or append if <2).
      - remove: pop index.
      - edit: set point.
    """
    max_number_points: int | None = None

    def add_point(self, path_points: list[Point], new_point: Point, closed: bool) -> list[Point]:
        pts = list(path_points)
        if self.max_number_points is not None and len(pts) >= self.max_number_points:
            return pts
        if not closed:
            pts.append(new_point)
            return pts
        if len(pts) < 2:
            pts.append(new_point)
            return pts
        i = best_edge_index_for_insertion(pts, new_point)
        if i is None:
            pts.append(new_point)
        else:
            pts.insert(i + 1, new_point)
        return pts

    def remove_point(self, path_points: list[Point], idx: int) -> list[Point]:
        if idx < 0 or idx >= len(path_points):
            return list(path_points)
        pts = list(path_points)
        pts.pop(idx)
        return pts

    def edit_point(self, path_points: list[Point], idx: int, edited_point: Point) -> list[Point]:
        if idx < 0 or idx >= len(path_points):
            return list(path_points)
        pts = list(path_points)
        pts[idx] = (float(edited_point[0]), float(edited_point[1]))
        return pts

    def segments(self, pts: list[Point], closed: bool, /):
        n = len(pts)
        if n < 2:
            return
        if n == 2 and not closed:
            return
        if closed:
            p = [pts[-1]] + list(pts) + [pts[0], pts[1]]
        else:
            p = [pts[0]] + list(pts) + [pts[-1]]
        for i in range(1, len(p) - 2):
            p0 = p[i - 1]; p1 = p[i]; p2 = p[i + 1]; p3 = p[i + 2]
            c1 = (p1[0] + (p2[0] - p0[0]) / 6.0,
                  p1[1] + (p2[1] - p0[1]) / 6.0)
            c2 = (p2[0] - (p3[0] - p1[0]) / 6.0,
                  p2[1] - (p3[1] - p1[1]) / 6.0)
            yield (c1, c2, p2)

    def fit_from_sample(self, sample: list[Point], closed: bool) -> list[Point]:
        """
        Downsample the given polyline to ≤ 8 control points (uniform by index).
        """
        if not sample:
            return []
        k = 8
        n = len(sample)
        if n <= k:
            return [ (float(x), float(y)) for x,y in sample ]
        out: list[Point] = []
        for i in range(k):
            j = int(round(i * (n - 1) / (k - 1)))
            x, y = sample[j]
            out.append((float(x), float(y)))
        return out

    def interpolate(self, pts: list[Point], closed: bool, n=100) -> list[Point]:
        """
        Sample n points along the spline via cubic segments.
        """
        return sample_cubic_path(pts, closed, self.segments, total=100)


@register_point_editor("circle")
class CirclePE(PointEditorComponent):
    max_number_points: int | None = 2
    default_closed = True

    def path_ops(self, pts: list[Point], closed: bool, /):
        if len(pts) < 2:
            return []
        cx, cy = pts[0]
        px, py = pts[1]
        rx = px - cx;
        ry = py - cy
        r = (rx * rx + ry * ry) ** 0.5
        if r <= 0.0:
            return []

        k = 0.5522847498307936
        a0 = (cx + r, cy)  # 0°
        a1 = (cx, cy + r)  # 90°
        a2 = (cx - r, cy)  # 180°
        a3 = (cx, cy - r)  # 270°

        # quarter 0: a0 -> a1
        c10 = (a0[0], a0[1] + k * r)
        c20 = (a1[0] + k * r, a1[1])
        # quarter 1: a1 -> a2
        c11 = (a1[0] - k * r, a1[1])
        c21 = (a2[0], a2[1] + k * r)
        # quarter 2: a2 -> a3
        c12 = (a2[0], a2[1] - k * r)
        c22 = (a3[0] - k * r, a3[1])
        # quarter 3: a3 -> a0
        c13 = (a3[0] + k * r, a3[1])
        c23 = (a0[0], a0[1] - k * r)

        return [
            ("M", a0),
            ("C", (c10, c20, a1)),
            ("C", (c11, c21, a2)),
            ("C", (c12, c22, a3)),
            ("C", (c13, c23, a0)),
            ("Z", ()),
        ]

    def add_point(self, path_points: list[Point], new_point: Point, closed: bool) -> list[Point]:
        # Always enforce 2 points: [center, on_radius]
        pts = list(path_points)
        if len(pts) == 0:
            c = (float(new_point[0]), float(new_point[1]))
            r = (c[0] + 100.0, c[1])  # default radius = 100 to the right
            return [c, r]
        if len(pts) == 1:
            return [pts[0], (float(new_point[0]), float(new_point[1]))]
        # already complete -> ignore extras
        return pts

    def remove_point(self, path_points: list[Point], idx: int) -> list[Point]:
        # Removing any point drops the circle (your previous behavior).
        return []

    def edit_point(self, path_points: list[Point], idx: int, edited_point: Point) -> list[Point]:
        if len(path_points) == 0:
            return []
        if len(path_points) == 1:
            if idx == 0:
                return [(float(edited_point[0]), float(edited_point[1]))]
            return list(path_points)
        c0x, c0y = path_points[0]
        r0x, r0y = path_points[1]
        if idx == 0:
            dx = float(edited_point[0]) - float(c0x)
            dy = float(edited_point[1]) - float(c0y)
            return [(float(edited_point[0]), float(edited_point[1])), (float(r0x + dx), float(r0y + dy))]
        if idx == 1:
            return [(float(c0x), float(c0y)), (float(edited_point[0]), float(edited_point[1]))]
        return list(path_points)

    def segments(self, pts: list[Point], closed: bool, /):
        if len(pts) < 2:
            return
        cx, cy = pts[0]
        px, py = pts[1]
        rx = px - cx; ry = py - cy
        r = (rx*rx + ry*ry) ** 0.5
        if r == 0.0:
            return
        k = 0.5522847498307936
        def seg(ax, ay, bx, by, cx2, cy2):
            c1 = (ax + k * (cx2 - ax), ay + k * (cy2 - ay))
            c2 = (bx + k * (cx2 - bx), by + k * (cy2 - by))
            return c1, c2, (bx, by)
        a0 = (cx + r, cy)
        a1 = (cx, cy + r)
        a2 = (cx - r, cy)
        a3 = (cx, cy - r)
        s0 = seg(a0[0], a0[1], a1[0], a1[1], cx, cy)
        s1 = seg(a1[0], a1[1], a2[0], a2[1], cx, cy)
        s2 = seg(a2[0], a2[1], a3[0], a3[1], cx, cy)
        s3 = seg(a3[0], a3[1], a0[0], a0[1], cx, cy)
        yield s0[0], s0[1], s0[2]
        yield s1[0], s1[1], s1[2]
        yield s2[0], s2[1], s2[2]
        yield s3[0], s3[1], s3[2]

    def fit_from_sample(self, sample: list[Point], closed: bool) -> list[Point]:
        """
        Coarse circle fit: center = mean of points, radius = mean distance to center.
        Fallback to default when sample too small.
        """
        n = len(sample)
        if n == 0:
            c = (0.0, 0.0)
            r = (100.0, 0.0)
            return [c, r]
        sx = 0.0; sy = 0.0
        for x, y in sample:
            sx += float(x); sy += float(y)
        cx = sx / n; cy = sy / n
        if n == 1:
            return [(cx, cy), (cx + 100.0, cy)]
        # mean radius
        sr = 0.0
        for x, y in sample:
            dx = float(x) - cx; dy = float(y) - cy
            sr += (dx*dx + dy*dy) ** 0.5
        r = sr / n if n > 0 else 100.0
        return [(cx, cy), (cx + r, cy)]

    def interpolate(self, pts: list[Point], closed: bool, n=100) -> list[Point]:
        """
        Sample n points along the circle using the cubic approximation.
        """
        return sample_cubic_path(pts, closed, self.segments, total=100)

