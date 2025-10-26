from PySide6 import QtCore, QtWidgets

from widgets import AbstractSplineOverlayWidget
from widgets.tools import ToolSelectorWidget


class Bar(QtWidgets.QToolBar):  # ← use a real toolbar
    def __init__(self, spline_overlay: AbstractSplineOverlayWidget):
        super().__init__()

        self.spline_overlay = spline_overlay
        self.reset_button = QtWidgets.QPushButton("reset")
        self.setObjectName("Bar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(18, 18))  # optional; remove if you prefer

        # Add your existing widget into the toolbar
        self.addWidget(ToolSelectorWidget())
        self.addWidget(self.reset_button)

        self.reset_button.clicked.connect(self._reset_overlay)

    @QtCore.Slot()
    def _reset_overlay(self):
        self.spline_overlay.clear()