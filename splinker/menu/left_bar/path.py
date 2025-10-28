from PySide6 import QtWidgets, QtCore

from splinker.menu.left_bar.layer_item import LayerItem
from splinker.widgets import Overlay


class PathTab(QtWidgets.QWidget):
    """
    Tab that lists *overlays*. Each row is an OverlayListItem that manages its own points.
    """
    layerSelected = QtCore.Signal(object)  # emits the selected overlay-like object (must expose `.spline`)

    def __init__(self, overlay: Overlay, parent=None):
        super().__init__(parent)
        self._list = QtWidgets.QListWidget(self)
        self._list.setUniformItemSizes(False)
        self._manager = overlay  # Overlay (multi-overlay) manager

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self._list)

        self._list.currentRowChanged.connect(self._on_row_changed)
        self.layerSelected.connect(self._apply_selection_to_manager)
        self._manager.layerNameChanged.connect(self._on_layer_name_changed)

        self._rebuild_from_manager()

    def _rebuild_from_manager(self):
        if self._manager is None:
            self._list.clear()
            return

        # Build rows using small overlay-like shims exposing `.spline`
        self._list.clear()
        for i in range(len(self._manager)):
            name = self._manager.layer_name_at(i)
            self.add_overlay(self._manager, name)

        # select active row
        idx = self._manager.get_active_idx()
        if 0 <= idx < self._list.count():
            self._list.setCurrentRow(idx)

        self._manager.overlaysChanged.connect(self._rebuild_from_manager)
        self._manager.activeLayerChanged.connect(self._select_active_row)
        self._manager.overlayUpdated.connect(self._refresh_row)

    def _refresh_row(self, idx: int):
        if 0 <= idx < self._list.count():
            item = self._list.item(idx)
            w = self._list.itemWidget(item)
            if isinstance(w, LayerItem):
                w.refresh()

    def _select_active_row(self, idx: int):
        if 0 <= idx < self._list.count():
            self._list.setCurrentRow(idx)

    # ---- existing API kept --------------------------------------------------
    def add_overlay(self, overlay: Overlay, name: str = ""):
        row_widget = LayerItem(overlay, name, self)
        row_widget.requestActivate.connect(self._emit_activate)

        item = QtWidgets.QListWidgetItem(self._list)
        item.setSizeHint(row_widget.sizeHint())
        self._list.addItem(item)
        self._list.setItemWidget(item, row_widget)
        return row_widget

    def set_overlays(self, overlays: list, names: list[str] | None = None):
        self._list.clear()
        for i, ov in enumerate(overlays):
            nm = names[i] if (names and i < len(names)) else f"Overlay {i+1}"
            self.add_overlay(ov, nm)

    def current_overlay(self):
        it = self._list.currentItem()
        if it is None:
            return None
        w = self._list.itemWidget(it)
        return w.overlay if isinstance(w, LayerItem) else None

    def refresh_all(self):
        for i in range(self._list.count()):
            w = self._list.itemWidget(self._list.item(i))
            if isinstance(w, LayerItem):
                w.refresh()

    def _on_row_changed(self, row: int):
        if row < 0:
            self.layerSelected.emit(None)
            return
        it = self._list.item(row)
        w = self._list.itemWidget(it)
        if isinstance(w, LayerItem):
            self.layerSelected.emit(w)

    def _emit_activate(self, overlay):
        self.layerSelected.emit(overlay)

    def _apply_selection_to_manager(self, overlay):
        """Called when the user clicks/selects an overlay in the list."""
        if self._manager is None or overlay is None:
            return
        try:
            cnt = len(self._manager)
            for i in range(cnt):
                if self._manager.spline_at(i) is overlay.spline:
                    self._manager.set_active_layer(i)
                    return
        except Exception:
            return

    def _on_layer_name_changed(self, idx: int):
        if 0 <= idx < self._list.count():
            item = self._list.item(idx)
            w = self._list.itemWidget(item)
            if isinstance(w, LayerItem):
                w.setName(self._manager.layer_name_at(idx))
