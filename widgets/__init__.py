from PySide6 import QtWidgets
from widgets.gradients import GradientWidget
from widgets.spline import AbstractSplineOverlayWidget, CatmullRomSplineOverlayWidget


class MainInterface(QtWidgets.QWidget):
    """
    Simple composite: a GradientWidget plus a SplineOverlayWidget stacked together.
    """
    def __init__(self,
                 gradient: GradientWidget,
                 spline_overlay: AbstractSplineOverlayWidget,
                 parent=None
                 ):
        super().__init__(parent)
        self._gradient = gradient
        self._spline_overlay = spline_overlay
        self._overlay = CatmullRomSplineOverlayWidget(gradient=self._gradient, parent=self)

        lay = QtWidgets.QStackedLayout(self)
        lay.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        lay.addWidget(self._gradient)
        lay.addWidget(self._overlay)

    @property
    def gradient(self):
        return self._gradient

    @property
    def overlay(self):
        return self._overlay
