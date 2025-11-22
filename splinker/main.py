import sys

from PySide6 import QtCore, QtWidgets

from splinker.core import HsvSquareGradient, CatmullRomSplinePE, Layer, Path, Palette
from splinker.menu import Bar, MenuBar, PaletteGradientBar
from splinker.widgets import CanvasWidget

class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QtWidgets.QHBoxLayout()
        self.layout = QtWidgets.QVBoxLayout(self)

        first_palette = Palette(
            "First Palette",
            [Layer(
                gradient=HsvSquareGradient(300, 300, 298, hue=0),
                path=Path(),
                name="Layer 1"
            )]
        )
        self.canvas = CanvasWidget(palette=first_palette, parent=self)

        self.menu_bar = MenuBar(self.canvas)
        self.top_bar = Bar(self.canvas)

        self.palette_bar = PaletteGradientBar(self.canvas, self)

        self.main_layout.addWidget(self.menu_bar)
        self.main_layout.addWidget(self.canvas, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.palette_bar,  alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.top_bar, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(self.main_layout)

        self.canvas.overlayUpdated.connect(self.menu_bar.refresh)
        self.canvas.display.pointsChanged.connect(self.menu_bar.refresh)
        self.menu_bar.tabChanged.connect(self.canvas.on_tab_changed)


if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    with open("./style/main.qss", "r") as f:
        app.setStyleSheet(f.read())

    widget = MyWidget()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())