from PySide6 import QtWidgets, QtCore

from splinker.menu.left_bar.layer_item import LayerItem
from splinker.widgets import CanvasWidget

from typing import Type
from splinker.core.gradients import Gradient
from splinker.widgets.editors import EditorFactory, IGradientEditor
from splinker.widgets import editor_registry


class PathTab(QtWidgets.QWidget):
    """
    Tab that lists *overlays*. Each row is an OverlayListItem that manages its own points.
    """
    layerSelected = QtCore.Signal(object)  # emits the selected overlay-like object (must expose `.spline`)

    def __init__(self, overlay: CanvasWidget, parent=None):
        super().__init__(parent)
        self._list = QtWidgets.QListWidget(self)
        self._list.setUniformItemSizes(False)
        self._overlay = overlay  # Overlay (multi-overlay) manager

        # --- editor host under the list (new) --------------------------------
        self._editor_box = QtWidgets.QGroupBox("Gradient", self)
        self._editor_box.setFlat(True)
        self._editor_lay = QtWidgets.QVBoxLayout(self._editor_box)
        self._editor_lay.setContentsMargins(0, 0, 0, 0)
        self._editor_widget: IGradientEditor | None = None
        self._editor_type: Type[IGradientEditor] | None = None

        placeholder = QtWidgets.QLabel("No gradient available", self._editor_box)
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._editor_lay.addWidget(placeholder)

        # layout: list on top, editor below
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(6, 6, 6, 6)
        lay.addWidget(self._list)
        lay.addWidget(self._editor_box)

        self._list.currentRowChanged.connect(self._on_row_changed)
        self.layerSelected.connect(self._refresh_editor_from_active)
        self._overlay.layerNameChanged.connect(self._on_layer_name_changed)


        self._rebuild_from_manager()

    def _rebuild_from_manager(self):
        if self._overlay is None:
            self._list.clear()
            self._clear_editor()
            return

        # Build rows using small overlay-like shims exposing `.spline`
        self._list.clear()
        for i in range(len(self._overlay)):
            name = self._overlay[i].name
            self.add_overlay(self._overlay, name)

        # select active row
        idx = self._overlay.get_active_idx()
        if 0 <= idx < self._list.count():
            self._list.setCurrentRow(idx)

        # (re-)connect only once per rebuild
        self._overlay.overlaysChanged.connect(self._rebuild_from_manager)
        self._overlay.activeLayerChanged.connect(self._select_active_row)
        self._overlay.activeLayerChanged.connect(self._refresh_editor_from_active)  # <- new
        self._overlay.overlayUpdated.connect(self._refresh_row)

        # sync editor with current
        self._refresh_editor_from_active()

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
    def add_overlay(self, overlay: CanvasWidget, name: str = ""):
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

    def _emit_activate(self, layer: LayerItem):
        assert isinstance(layer, LayerItem)
        self.layerSelected.emit(layer)


    def _on_layer_name_changed(self, idx: int):
        if 0 <= idx < self._list.count():
            item = self._list.item(idx)
            w = self._list.itemWidget(item)
            if isinstance(w, LayerItem):
                w.setName(self._overlay[idx].name)

    # ---- editor wiring (new) ------------------------------------------------

    def _clear_editor(self):
        # remove all children from the editor layout
        while self._editor_lay.count():
            it = self._editor_lay.takeAt(0)
            w = it.widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        self._editor_widget = None
        self._editor_type = None
        # placeholder
        ph = QtWidgets.QLabel("No gradient available", self._editor_box)
        ph.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self._editor_lay.addWidget(ph)

    def _refresh_editor_from_active(self, *args):
        """
        Swap in the proper editor for the active layer's gradient,
        and push the current gradient into the editor.
        """

        layer_widget = self._overlay.active_layer  # LayerOverlayWidget
        pure_grad = layer_widget.gradient  # This is already a Gradient

        if pure_grad is None:
            self._clear_editor()
            return

        # Find a factory for this gradient type
        g_cls = type(pure_grad)
        factory: EditorFactory | None = editor_registry.get(g_cls)

        if factory is None:
            # no editor registered → show placeholder
            self._clear_editor()
            return

        # Create or reuse the editor if type matches
        ed = self._editor_widget
        if ed is None or type(ed) is not type(factory()):
            # Remove old widget(s) without adding placeholder
            while self._editor_lay.count():
                it = self._editor_lay.takeAt(0)
                w = it.widget()
                if w is not None:
                    w.setParent(None)
                    w.deleteLater()

            # Create new editor
            ed = factory()
            ed.gradientChanged.connect(self._apply_editor_gradient_to_active)
            self._editor_lay.addWidget(ed)
            self._editor_widget = ed
            self._editor_widget.gradientChanged.connect(self._overlay.apply_gradient_from_editor)
            self._editor_type = type(ed)

        # load current gradient into the editor
        if ed is not None:
            ed.setGradient(pure_grad)

    @QtCore.Slot(object)
    def _apply_editor_gradient_to_active(self, new_grad: Gradient):
        """
        Apply the edited pure gradient back into the active GradientOverlayWidget.
        """
        layer = self._overlay.active_layer
        if layer is None or new_grad is None:
            return

        layer.gradient = new_grad
        self._overlay.display.update()
        idx = self._overlay.get_active_idx()
        self._overlay.overlayUpdated.emit(idx)
