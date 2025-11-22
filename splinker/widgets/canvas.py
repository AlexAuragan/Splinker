from PySide6 import QtWidgets, QtCore

from splinker.core import Layer, Gradient
from splinker.core.palette import Palette

from splinker.widgets.layer_display import PaletteDisplayComponent


class CanvasWidget(QtWidgets.QWidget):
    """
    View/controller for a Palette.
    Holds a single LayerDisplayComponent that always displays the Palette's active layer.
    """

    overlaysChanged = QtCore.Signal()          # emitted when overlays (layers) are added/removed
    activeLayerChanged = QtCore.Signal(int)    # emitted when the active index changes
    overlayUpdated = QtCore.Signal(int)        # emitted when an overlay content updates (points/colors), arg = index
    layerNameChanged = QtCore.Signal(int)      # emitted when a layer's name changes (arg = index)

    def __init__(self, palette: Palette, parent=None):
        super().__init__(parent)

        # model
        self._palette: Palette = palette

        # single display component bound to the active layer
        self._display = PaletteDisplayComponent(palette=self._palette, parent=self)
        self._display.pointsChanged.connect(self._emit_overlay_updated_for_active)

        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addWidget(self._display)

    # --- public API -------------------------
    @property
    def active_layer(self) -> Layer:
        return self._palette.active_layer

    @property
    def display(self) -> PaletteDisplayComponent:
        return self._display

    def get_active_idx(self) -> int:
        return self._palette.active_idx

    def set_layer_name(self, index: int, name: str) -> None:
        if not (0 <= index < len(self._palette)):
            return
        nm = name if isinstance(name, str) else ""
        if self._palette[index].name != nm:
            self._palette.set_layer_name(index, nm)
            if index == self._palette.active_idx:
                # repaint enough for debug overlays / titles if any
                self._display.update()
            self.layerNameChanged.emit(index)

    def remove_layer(self, index: int) -> bool:
        if not (0 <= index < len(self._palette)):
            return False
        removing_active = (index == self._palette.active_idx)
        ok = self._palette.remove_layer(index)
        if not ok:
            return False

        # notify display that active may have changed
        if removing_active:
            self._display.notify_active_layer_changed()
        elif self._palette.active_idx >= 0:
            self._display.notify_active_layer_changed()

        self.overlaysChanged.emit()
        if self._palette.active_idx >= 0:
            self.activeLayerChanged.emit(self._palette.active_idx)
        return True

    def add_layer(self, layer: Layer) -> int:
        if not isinstance(layer, Layer):
            raise TypeError("add_layer expects a splinker.core.layer.Layer")
        idx = self._palette.add_layer(layer)

        # If a first layer was added, or palette chose to make it active, refresh
        self._display.notify_active_layer_changed()

        self.overlaysChanged.emit()
        self.overlayUpdated.emit(idx)
        return idx

    def set_active_layer(self, index: int) -> None:
        if 0 <= index < len(self._palette):
            self._palette.set_active(index)
            self._display.notify_active_layer_changed()
            self.activeLayerChanged.emit(index)

    def count(self) -> int:
        return len(self._palette)


    def duplicate_layer(self, index: int | str) -> int:
        if isinstance(index, str):
            # map name to index
            found = -1
            for i in range(len(self._palette)):
                if self._palette[i].name == index:
                    found = i
                    break
            if found == -1:
                raise KeyError(index)
            index = found
        if not isinstance(index, int):
            raise TypeError("index must be int or str")

        new_idx = self._palette.duplicate_layer(index)
        self._display.notify_active_layer_changed()
        self.overlaysChanged.emit()
        self.overlayUpdated.emit(new_idx)
        return new_idx

    def __getitem__(self, key) -> Layer:
        """Allow canvas['Layer 1'] or canvas[0] access to the *Layer model*."""
        return self._palette[key]

    def __len__(self):
        return len(self._palette)

    # --- internals --------------------------
    def _emit_overlay_updated_for_active(self):
        idx = self._palette.active_idx
        if idx != -1:
            self.overlayUpdated.emit(idx)

    @QtCore.Slot(object)
    def apply_gradient_from_editor(self, grad: Gradient) -> None:
        """
        Slot to receive Gradient objects from an editor and apply them
        to the active layer, then refresh the display and emit signals.
        """
        if self._palette.active_idx < 0:
            return
        layer = self._palette.active_layer
        layer.gradient = grad  # update the pure-Python model

        # tell the display that the gradient object changed
        self._display.notify_gradient_changed()

        # keep external listeners informed
        idx = self._palette.active_idx
        self.overlayUpdated.emit(idx)

    def on_tab_changed(self, name):
        match name:
            case "Path":
                self.display.path_editor_dc.activate()
                self.display.distribution_editor_dc.deactivate()
            case "Palette":
                self.display.path_editor_dc.deactivate()
                self.display.distribution_editor_dc.activate()
            case "Actions":
                self.display.path_editor_dc.deactivate()
                self.display.distribution_editor_dc.deactivate()
            case _:
                raise ValueError(name)