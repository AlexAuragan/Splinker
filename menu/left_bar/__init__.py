from PySide6 import QtWidgets, QtCore, QtGui

from menu.left_bar.gradiant_bar import PaletteGradientBar
from menu.left_bar.path import PathTab


class MenuBar(QtWidgets.QTabWidget):
    """
    Simple tabbed menu:
      - Path: lists spline control points.
      - Palette: placeholder for future color list.
      - Actions: placeholder for future commands.
    """
    def __init__(self, parent=None):
        super().__init__(parent)

        # Tabs
        self._path_tab = PathTab(self)
        self._palette_tab = QtWidgets.QWidget(self)
        self._actions_tab = QtWidgets.QWidget(self)

        pal_lay = QtWidgets.QHBoxLayout()
        pal_lay.setContentsMargins(6, 6, 6, 6)
        pal_lay.setSpacing(6)
        self._palette_bar = PaletteGradientBar(self._palette_tab)
        pal_lay.addWidget(self._palette_bar)
        pal_lay.addStretch(1)  # room for future widgets
        self._palette_tab.setLayout(pal_lay)

        # Basic placeholder layouts for future tabs
        self._palette_tab.setLayout(QtWidgets.QVBoxLayout())
        self._palette_tab.layout().addStretch(1)

        self._actions_tab.setLayout(QtWidgets.QVBoxLayout())
        self._actions_tab.layout().addStretch(1)

        # Add tabs
        self.addTab(self._path_tab, "Path")
        self.addTab(self._palette_tab, "Palette")
        self.addTab(self._actions_tab, "Actions")

    # ---- public helpers -----------------------------------------------------
    def set_spline(self, spline, /):
        """
        Provide the spline overlay widget so the Path tab can read its points.
        """
        self._path_tab.set_spline(spline)

    def set_points(self, pts: list[QtCore.QPointF], /):
        """
        Optional explicit population without passing a spline.
        """
        self._path_tab.set_points(pts)

    def refresh(self, /):
        """
        Re-scan the spline (if set) and update the Path list.
        Call this after edits to the control points.
        """
        self._path_tab.refresh()


__all__ = [
    "MenuBar"
]