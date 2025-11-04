import sys

from PySide6 import QtCore, QtWidgets

from splinker.core import HsvSquareGradient, CatmullRomSplinePE, Layer, Path, Palette
from splinker.menu import Bar, MenuBar, PaletteGradientBar
from splinker.widgets import CanvasWidget, LayerDisplayComponent

class MyWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()

        self.main_layout = QtWidgets.QHBoxLayout()
        self.layout = QtWidgets.QVBoxLayout(self)

        first_palette = Palette(
            "First Palette",
            [Layer(
                gradient=HsvSquareGradient(300, 300, 298, hue=0),
                path=Path(editor=CatmullRomSplinePE()),
                name="Layer 1"
            )]
        )
        self.overlay = CanvasWidget(palette=first_palette, parent=self)

        self.menu_bar = MenuBar(self.overlay)
        self.top_bar = Bar(self.overlay)

        self.palette_bar = PaletteGradientBar(self.overlay,self)

        self.main_layout.addWidget(self.menu_bar)
        self.main_layout.addWidget(self.overlay, alignment=QtCore.Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.palette_bar,  alignment=QtCore.Qt.AlignmentFlag.AlignRight)
        self.layout.addWidget(self.top_bar, alignment=QtCore.Qt.AlignmentFlag.AlignTop)
        self.layout.addLayout(self.main_layout)

        self.overlay.overlayUpdated.connect(self.menu_bar.refresh)
        self.overlay.display.pointsChanged.connect(self.menu_bar.refresh)



if __name__ == "__main__":
    app = QtWidgets.QApplication([])

    with open("./style/main.qss", "r") as f:
        app.setStyleSheet(f.read())

    widget = MyWidget()
    widget.resize(800, 600)
    widget.show()

    sys.exit(app.exec())