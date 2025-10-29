from .gradients import Gradient, HsvWheelGradient, HsvSquareGradient
from .splines import Spline, CatmullRomSpline

gradient_registry = {
    "HSV Wheel": HsvWheelGradient,
    "HSV Square": HsvSquareGradient
}
spline_registry = {
    "Catmull Rom": CatmullRomSpline,
}
