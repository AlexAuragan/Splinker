from abc import ABC, abstractmethod
from typing import Iterable, Sequence, Tuple, List, Literal, Optional

Point = Tuple[float, float]
Op = Tuple[Literal["M", "L", "C", "Z"], tuple]

def _dist2(a: Point, b: Point) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return dx*dx + dy*dy

def _orientation(a: Point, b: Point, c: Point) -> float:
    # cross((b-a),(c-b))
    return (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])

def _signed_area(pts: Sequence[Point]) -> float:
    n = len(pts)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        j = (i + 1) % n
        s += pts[i][0] * pts[j][1] - pts[j][0] * pts[i][1]
    return 0.5 * s

def _poly_orientation_sign(pts: Sequence[Point]) -> int:
    area = _signed_area(pts)
    return 1 if area > 0 else (-1 if area < 0 else 0)

def _edge_delta_len(a: Point, b: Point, p: Point) -> float:
    import math
    def d(u: Point, v: Point) -> float:
        return math.hypot(u[0]-v[0], u[1]-v[1])
    return d(a, p) + d(p, b) - d(a, b)

def _project_point_to_segment(p: Point, a: Point, b: Point) -> Point:
    ax, ay = a; bx, by = b; px, py = p
    vx, vy = bx - ax, by - ay
    denom = vx*vx + vy*vy
    if denom == 0.0:
        return a
    t = ((px - ax) * vx + (py - ay) * vy) / denom
    if t < 0.0: t = 0.0
    elif t > 1.0: t = 1.0
    return ax + t * vx, ay + t * vy

def _edge_valid_for_convex_insert(pts: Sequence[Point], i: int, p: Point, sgn: int) -> bool:
    n = len(pts)
    im1 = (i - 1) % n
    ip1 = (i + 1) % n
    ip2 = (i + 2) % n
    o1 = _orientation(pts[im1], pts[i],   p)
    o2 = _orientation(pts[i],   p,        pts[ip1])
    o3 = _orientation(p,        pts[ip1], pts[ip2])
    if sgn > 0:
        return (o1 >= 0.0) and (o2 >= 0.0) and (o3 >= 0.0)
    else:
        return (o1 <= 0.0) and (o2 <= 0.0) and (o3 <= 0.0)

def _best_convex_insert_index(pts: Sequence[Point], p: Point) -> Optional[int]:
    n = len(pts)
    if n < 3:
        return None
    sgn = _poly_orientation_sign(pts)
    if sgn == 0:
        return None
    best_i = None
    best_delta = float("inf")
    for i in range(n):
        j = (i + 1) % n
        if _edge_valid_for_convex_insert(pts, i, p, sgn):
            dl = _edge_delta_len(pts[i], pts[j], p)
            if dl < best_delta:
                best_delta = dl
                best_i = i
    return best_i


class Spline(ABC):
    """
    GUI-agnostic spline interface.
    """

    @abstractmethod
    def segments(self, pts: Sequence[Point], closed: bool, /) -> Iterable[Tuple[Point, Point, Point]]:
        """
        Yield (c1, c2, p2) for each cubic segment, assuming a moveTo at pts[0].
        """

    # ---- convenience built on top of `segments` ----------------------------
    def path_ops(self, pts: Sequence[Point], closed: bool, /) -> List[Op]:
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
        ops: List[Op] = [("M", pts[0])]
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

    # ---- convex insertion helper (data-side) -------------------------------
    def insert_point_convex(self, pts: Sequence[Point], p: Point, closed: bool, /) -> Tuple[Sequence[Point], bool]:
        """
        Try to insert p keeping convexity (if `closed` and len(pts)>=3).
        Returns (new_points, inserted_flag). Falls back by projecting to the nearest edge.
        """
        if not closed or len(pts) < 3:
            return (pts, False)

        i = _best_convex_insert_index(pts, p)
        if i is not None:
            new_pts = list(pts)
            new_pts.insert(i + 1, p)
            return (new_pts, True)

        # Fallback: project to nearest edge
        n = len(pts)
        best_i = 0
        best_d2 = float("inf")
        best_q = None
        for k in range(n):
            j = (k + 1) % n
            q = _project_point_to_segment(p, pts[k], pts[j])
            d2 = _dist2(q, p)
            if d2 < best_d2:
                best_d2 = d2
                best_i = k
                best_q = q
        if best_q is not None:
            new_pts = list(pts)
            new_pts.insert(best_i + 1, best_q)
            return (new_pts, True)

        return (pts, False)


class CatmullRomSpline(Spline):
    def segments(self, pts: Sequence[Point], closed: bool, /) -> Iterable[Tuple[Point, Point, Point]]:
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
