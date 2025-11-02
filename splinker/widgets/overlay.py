from PySide6 import QtWidgets, QtCore
from splinker.widgets.layer_overlay import LayerOverlayWidget


class Overlay(QtWidgets.QWidget):
    """
    Manages one or more Layers and only displays the active one.
    """

    overlaysChanged = QtCore.Signal()          # emitted when overlays are added/removed
    activeLayerChanged = QtCore.Signal(int)    # emitted when the active index changes
    overlayUpdated = QtCore.Signal(int)        # emitted when an overlay content updates (points/colors), arg = index
    layerNameChanged = QtCore.Signal(int)      # emitted when a layer's name changes (arg = index)

    def __init__(self,
                 layer: LayerOverlayWidget | None = None,
                 parent=None
                 ):
        super().__init__(parent)

        self._stack = QtWidgets.QStackedLayout(self)
        self._stack.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackOne)

        self._layers: list[LayerOverlayWidget] = []
        self._active_idx = -1

        self.add_layer(layer)
        self.set_active_layer(0)

    # --- public API -------------------------
    @property
    def active_layer(self) -> LayerOverlayWidget:
        return self._layers[self._active_idx]

    def get_active_idx(self):
        return self._active_idx

    def set_layer_name(self, index: int, name: str) -> None:
        """Set the display name for a layer and notify listeners."""
        if 0 <= index < len(self._layers):
            nm = name if isinstance(name, str) else ""
            if self._layers[index].name != nm:
                self._layers[index].set_name(nm)
                self.layerNameChanged.emit(index)

    def remove_layer(self, index: int) -> bool:
        """Remove layer at index. Returns True if successful."""
        if not (0 <= index < len(self._layers)):
            return False

        layer = self._layers.pop(index)
        self._stack.removeWidget(layer)
        layer.deleteLater()

        # Adjust active index if needed
        if self._active_idx >= len(self._layers):
            self._active_idx = len(self._layers) - 1

        self.overlaysChanged.emit()
        if self._active_idx >= 0:
            self.activeLayerChanged.emit(self._active_idx)

        return True

    def add_layer(self, layer: LayerOverlayWidget | None) -> int:
        # grad = gradient or GradientOverlayWidget(HsvWheelGradient(300, 300, 298))
        layer = layer or LayerOverlayWidget()

        idx = len(self._layers)
        self._layers.append(layer)
        self._stack.addWidget(layer)

        layer.pointsChanged.connect(lambda i=idx: self.overlayUpdated.emit(i))
        self.overlaysChanged.emit()
        self.overlayUpdated.emit(idx)
        return idx

    def set_active_layer(self, index: int) -> None:
        if 0 <= index < self._stack.count():
            self._active_idx = index
            self._stack.setCurrentIndex(index)
            self.activeLayerChanged.emit(index)

    def count(self) -> int:
        return self._stack.count()

    def duplicate_layer(self, index: int | str):
        original = self[index]

        # Create new layer with copied data
        from splinker.core.layer import Layer
        from copy import deepcopy

        new_layer_data = Layer(
            gradient=original.gradient,  # Gradients are typically immutable
            path=deepcopy(original.path),  # Deep copy the path
            name=f"{original.name} Copy"
        )

        new_widget = LayerOverlayWidget(new_layer_data)
        return self.add_layer(new_widget)

    def __getitem__(self, key) -> LayerOverlayWidget:
        """Allow overlay['Layer 1'] or overlay[0] access."""
        if isinstance(key, int):
            if 0 <= key < len(self._layers):
                return self._layers[key]
            raise IndexError(key)
        if isinstance(key, str):
            for i, layer in enumerate(self._layers):
                if layer.name == key:
                    return layer
            raise KeyError(key)
        raise TypeError("key must be int or str")

    def __len__(self):
        return len(self._layers)