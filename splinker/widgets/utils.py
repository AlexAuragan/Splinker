from PySide6 import QtCore

from splinker.core import Point


def qpoint_to_point(p: QtCore.QPointF) -> Point:
    return float(p.x()), float(p.y())

def point_to_qpoint(p: Point) -> QtCore.QPointF:
    return QtCore.QPointF(p[0], p[1])
