from PySide6 import QtWidgets, QtCore

from splinker.menu.gradiant_bar import PaletteGradientBar
from splinker.menu.left_bar.path import PathTab
from splinker.widgets import Overlay


class MenuBar(QtWidgets.QTabWidget):
    """
    Simple tabbed menu:
      - Path: lists overlays; each overlay row manages its own point list.
      - Palette: placeholder for future color list.
      - Actions: placeholder for future commands.
    """
    overlaySelected = QtCore.Signal(object)

    def __init__(self, overlay: Overlay, parent=None):
        super().__init__(parent)

        self._overlay = overlay
        self._path_tab = PathTab(self._overlay ,self)
        self._palette_tab = QtWidgets.QWidget(self)
        self._actions_tab = QtWidgets.QWidget(self)

        self._palette_tab.setLayout(QtWidgets.QVBoxLayout())
        self._palette_tab.layout().addStretch(1)

        self._actions_tab.setLayout(QtWidgets.QVBoxLayout())
        self._actions_tab.layout().addStretch(1)

        self.addTab(self._path_tab, "Path")
        self.addTab(self._palette_tab, "Palette")
        self.addTab(self._actions_tab, "Actions")

        self._path_tab.layerSelected.connect(self.overlaySelected)


    def current_overlay(self, /):
        return self._path_tab.current_overlay()

    def set_points(self, pts: list[QtCore.QPointF], /):
        return

    def refresh(self, /):
        self._path_tab.refresh_all()


__all__ = [
    "MenuBar",
    "PaletteGradientBar"
]