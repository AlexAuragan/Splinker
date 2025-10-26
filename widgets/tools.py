from enum import Enum
from typing import Callable, Any

from PySide6 import QtCore, QtWidgets, QtGui
from PySide6.QtCore import Qt, Signal

class ToolMode(Enum):
    SPLINE = "Spline"
    ELLIPSIS = "Ellipsis"

class ToolSelectorWidget(QtWidgets.QWidget):


    mode_changed = Signal(ToolMode)
    def __init__(self):
        super().__init__()

        self.select_box = QtWidgets.QComboBox()

        # self.select_box.addItem([ToolMode.SPLINE, ToolMode.ELLIPSIS ],["Spline", "Ellipsis"])
        self.select_box.addItem(ToolMode.SPLINE.value, ToolMode.SPLINE.name)
        self.select_box.addItem(ToolMode.ELLIPSIS.value, ToolMode.ELLIPSIS.name)
        self.text = QtWidgets.QLabel("Mode: ")
        self.layout = QtWidgets.QHBoxLayout(self)

        self.layout.addWidget(self.text, alignment=Qt.AlignmentFlag.AlignLeft)
        self.layout.addWidget(self.select_box, alignment=Qt.AlignmentFlag.AlignLeft)

        self.select_box.currentTextChanged.connect(self._on_mode_changed)



    @property
    def mode(self):
        return self.select_box.currentData().value


    def _on_mode_changed(self, text: str):
        mode = ToolMode(text)
        self.mode_changed.emit(mode)
