import sys

from PySide6 import QtCore, QtWidgets

from menu.bar import Bar
from menu.left_bar import MenuBar, PaletteGradientBar
from widgets import MainInterface, CatmullRomSplineOverlayWidget
from widgets.gradients import GradientCircleWidget


class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QtWidgets.QHBoxLayout()
        self.layout = QtWidgets.QVBoxLayout(self)

        self.menu_bar = MenuBar()
        self.gradient = GradientCircleWidget()
        self.overlay = CatmullRomSplineOverlayWidget(self.gradient)
        self.main_interface = MainInterface(self.gradient, self.overlay)
        self.top_bar = Bar(self.overlay)
        self.palette_bar = PaletteGradientBar(self)
        self.palette_bar.set_spline(self.overlay)

        self.main_layout.addWidget(self.menu_bar)
        self.main_layout.addWidget(self.main_interface, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.palette_bar,  alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.top_bar, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(self.main_layout)

        self.menu_bar.set_spline(self.overlay)
        self.overlay.pointsChanged.connect(self.menu_bar.refresh)




if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    with open("style/main.qss", "r") as f:
        app.setStyleSheet(f.read())

    widget = MyWidget()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())