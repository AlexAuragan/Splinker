from PySide6 import QtWidgets, QtCore

from splinker.menu.left_bar.layer_item import LayerItem
from splinker.widgets import Overlay

# NEW imports (minimal + necessary)
from typing import Type
from splinker.core.gradients import Gradient as CoreGradient
from splinker.widgets.editors import EditorFactory, IGradientEditor
from splinker.widgets import editor_registry


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
        self.layerSelected.connect(self._apply_selection_to_manager)
        self.layerSelected.connect(self._refresh_editor_from_active)   # <- new
        self._manager.layerNameChanged.connect(self._on_layer_name_changed)

        self._rebuild_from_manager()

    def _rebuild_from_manager(self):
        if self._manager is None:
            self._list.clear()
            self._clear_editor()
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

        # (re-)connect only once per rebuild
        self._manager.overlaysChanged.connect(self._rebuild_from_manager)
        self._manager.activeLayerChanged.connect(self._select_active_row)
        self._manager.activeLayerChanged.connect(self._refresh_editor_from_active)  # <- new
        self._manager.overlayUpdated.connect(self._refresh_row)

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
        try:
            grad_widget = self._manager.gradient  # GradientOverlayWidget
        except Exception:
            self._clear_editor()
            return
        if grad_widget is None:
            self._clear_editor()
            return

        pure_grad: CoreGradient | None = getattr(grad_widget, "gradient", None)
        if pure_grad is None:
            self._clear_editor()
            return

        # Find a factory for this gradient type (exact match first)
        g_cls = type(pure_grad)
        factory: EditorFactory | None = editor_registry.get(g_cls)
        if factory is None:
            # no editor registered → show placeholder
            self._clear_editor()
            return

        # Create or reuse the editor if type matches
        ed = self._editor_widget
        if ed is None or type(ed) is not type(factory()):
            # replace editor widget
            self._clear_editor()
            ed = factory()
            # when user changes params in editor, apply back to the gradient overlay
            ed.gradientChanged.connect(self._apply_editor_gradient_to_active)
            self._editor_lay.addWidget(ed)
            self._editor_widget = ed
            self._editor_type = type(ed)

        # load current gradient into the editor (won't emit if your editor blocks signals)
        if ed is not None:
            ed.setGradient(pure_grad)

    @QtCore.Slot(object)
    def _apply_editor_gradient_to_active(self, new_grad: CoreGradient):
        """
        Apply the edited pure gradient back into the active GradientOverlayWidget.
        """
        try:
            grad_widget = self._manager.gradient  # GradientOverlayWidget
        except Exception:
            return
        if grad_widget is None or new_grad is None:
            return
        try:
            # GradientOverlayWidget exposes set_gradient(...)
            grad_widget.set_gradient(new_grad)
            grad_widget.update()
        except Exception:
            pass
