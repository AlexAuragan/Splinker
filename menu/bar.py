from PySide6 import QtCore, QtWidgets
from widgets.tools import ToolSelectorWidget


class Bar(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()



        self.tool_selector = ToolSelectorWidget()

        self.layout = QtWidgets.QHBoxLayout(self)
        self.layout.addWidget(self.tool_selector, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)

