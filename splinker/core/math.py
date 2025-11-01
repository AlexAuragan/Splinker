from typing import Literal
Point = tuple[float, float]
Op = tuple[Literal["M", "L", "C", "Z"], tuple]

def project_point_to_segment(p: Point, a: Point, b: Point) -> tuple[Point, float]:
    ax, ay = a; bx, by = b; px, py = p
    vx, vy = bx - ax, by - ay
    denom = vx * vx + vy * vy
    if denom == 0.0:
        dx = px - ax; dy = py - ay
        return a, dx * dx + dy * dy
    t = ((px - ax) * vx + (py - ay) * vy) / denom
    if t < 0.0:
        qx, qy = ax, ay
    elif t > 1.0:
        qx, qy = bx, by
    else:
        qx, qy = ax + t * vx, ay + t * vy
    dx = px - qx; dy = py - qy
    return (qx, qy), dx * dx + dy * dy


def best_edge_index_for_insertion(path_points: list[Point], new_point: Point) -> int | None:
    """
    Return the index i of the edge (i -> i+1) that is closest to new_point by
    projection distance. For closed=True, includes the wrap edge (n-1 -> 0).
    Inserting at i+1 will place the new point on that edge.
    """
    n = len(path_points)
    if n == 0:
        return None
    if n == 1:
        return 0

    best_i = 0
    best_d2 = float("inf")

    edge_count = n
    for k in range(edge_count):
        i = k
        j = (i + 1) % n
        _, d2 = project_point_to_segment(new_point, path_points[i], path_points[j])
        # <= makes tie-breaking stable toward later edges; use < if you prefer earlier
        if d2 <= best_d2:
            best_d2 = d2
            best_i = i

    return best_i


def _cubic_eval(p0: Point, c1: Point, c2: Point, p3: Point, t: float) -> Point:
    u = 1.0 - t
    uu = u * u
    tt = t * t
    uuu = uu * u
    ttt = tt * t
    x = uuu * p0[0] + 3.0 * uu * t * c1[0] + 3.0 * u * tt * c2[0] + ttt * p3[0]
    y = uuu * p0[1] + 3.0 * uu * t * c1[1] + 3.0 * u * tt * c2[1] + ttt * p3[1]
    return (x, y)

def sample_cubic_path(pts: list[Point], closed: bool, seg_fn, total: int = 100) -> list[Point]:
    """
    Sample 'total' points across all cubic segments returned by seg_fn(pts, closed).
    Segments share samples evenly (simple and fast).
    """
    if not pts:
        return []
    # collect all segments and reconstruct p0 advancing along the path
    segs = list(seg_fn(pts, closed))
    if not segs:
        # handle the open-line 2-point case
        if len(pts) == 2 and not closed:
            p0 = pts[0]; p1 = pts[1]
            out: list[Point] = []
            for i in range(total):
                t = i / max(1, total - 1)
                x = p0[0] + (p1[0] - p0[0]) * t
                y = p0[1] + (p1[1] - p0[1]) * t
                out.append((x, y))
            return out
        return [pts[0]]

    # p0 starts at moveTo
    p0 = pts[0]
    m = len(segs)
    per = max(1, total // m)
    out: list[Point] = []
    for idx, (c1, c2, p2) in enumerate(segs):
        for i in range(per):
            t = i / per
            out.append(_cubic_eval(p0, c1, c2, p2, t))
        p0 = p2
    # ensure last endpoint is included
    out.append(p0)
    # trim/extend to total if necessary
    if len(out) > total:
        step = (len(out) - 1) / (total - 1)
        sel: list[Point] = []
        for i in range(total):
            j = int(round(i * step))
            sel.append(out[j])
        return sel
    return out