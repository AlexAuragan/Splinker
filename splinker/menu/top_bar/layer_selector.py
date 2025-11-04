from PySide6 import QtWidgets, QtCore

from splinker.core.layer import Layer
from splinker.widgets import CanvasWidget


class LayerSwitchWidget(QtWidgets.QWidget):
    """
    Minimal widget: one button to add overlays, one combobox to select which to show.
    """
    overlayChanged = QtCore.Signal(int)

    def __init__(self, overlay_manager: CanvasWidget):
        super().__init__()
        self._overlay = overlay_manager

        self._btn_new = QtWidgets.QPushButton("New overlay")
        self._select = QtWidgets.QComboBox()

        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._btn_new)
        lay.addWidget(self._select)

        # populate based on current overlays (prefer real names)
        for i in range(len(self._overlay)):
            name = self._overlay[i].name
            self._select.addItem(name)

        # if manager already has an active index, prefer it
        idx0 = self._overlay.get_active_idx()
        self._select.setCurrentIndex(idx0 if 0 <= idx0 < self._select.count() else 0)

        self._btn_new.clicked.connect(self._on_new)
        self._select.currentIndexChanged.connect(self._on_select_changed)

        # --- keep UI in sync with manager ---
        self._overlay.overlaysChanged.connect(self._rebuild)
        self._overlay.activeLayerChanged.connect(self._on_active_changed)
        self._overlay.layerNameChanged.connect(self._on_name_changed)

    @QtCore.Slot()
    def _on_new(self):
        idx = len(self._overlay)
        idx = self._overlay.add_layer(Layer(name=f"Layer {idx+1}"))
        self._select.setCurrentIndex(idx)  # triggers switch via _on_select_changed

    @QtCore.Slot(int)
    def _on_select_changed(self, idx: int):
        self._overlay.set_active_layer(idx)
        self.overlayChanged.emit(idx)

    # --- helpers ---
    @QtCore.Slot()
    def _rebuild(self):
        cur = self._select.currentIndex()
        self._select.blockSignals(True)
        self._select.clear()
        for i in range(len(self._overlay)):
            name = self._overlay[i].name or f"Overlay {i + 1}"
            self._select.addItem(name)
        if 0 <= cur < self._select.count():
            self._select.setCurrentIndex(cur)
        elif self._select.count() > 0:
            self._select.setCurrentIndex(0)
        self._select.blockSignals(False)

    @QtCore.Slot(int)
    def _on_active_changed(self, idx: int):
        if idx != self._select.currentIndex():
            self._select.blockSignals(True)
            self._select.setCurrentIndex(idx)
            self._select.blockSignals(False)

    @QtCore.Slot(int)
    def _on_name_changed(self, idx: int):
        if 0 <= idx < self._select.count():
            name = self._overlay[idx].name
            self._select.setItemText(idx, name)
