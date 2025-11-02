from PySide6 import QtCore, QtWidgets

from splinker.widgets import Overlay
from splinker.menu.top_bar.tools import ToolSelectorWidget
from splinker.menu.top_bar.layer_selector import LayerSwitchWidget


class Bar(QtWidgets.QToolBar):
    def __init__(self, overlay: Overlay):
        super().__init__()

        self.overlay = overlay
        self.reset_button = QtWidgets.QPushButton("reset")
        self.setObjectName("Bar")
        self.setMovable(False)
        self.setFloatable(False)
        self.setIconSize(QtCore.QSize(18, 18))
        self.overlay_selector = LayerSwitchWidget(self.overlay)

        # Add your existing widget into the toolbar
        # self.addWidget(ToolSelectorWidget())
        self.addWidget(self.reset_button)
        self.addWidget(self.overlay_selector)

        self.reset_button.clicked.connect(self._reset_overlay)

    @QtCore.Slot()
    def _reset_overlay(self):
        self.overlay.active_layer.path.clear()
        self.overlay.update()