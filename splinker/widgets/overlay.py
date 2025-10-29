from PySide6 import QtWidgets, QtCore

from splinker.core.gradients import HsvWheelGradient, HsvSquareGradient
from splinker.widgets.gradients_overlay import GradientOverlayWidget
from splinker.widgets.spline_overlay import SplineOverlayWidget


class Overlay(QtWidgets.QWidget):
    """
    Manages one or more (GradientOverlayWidget + SplineOverlayWidget) pairs and
    only displays the active one.
    """

    overlaysChanged = QtCore.Signal()          # emitted when overlays are added/removed
    activeLayerChanged = QtCore.Signal(int)    # emitted when the active index changes
    overlayUpdated = QtCore.Signal(int)        # emitted when an overlay content updates (points/colors), arg = index
    layerNameChanged = QtCore.Signal(int)      # emitted when a layer's name changes (arg = index)

    def __init__(self,
                 gradient: GradientOverlayWidget | None = None,
                 spline: SplineOverlayWidget | None = None,
                 parent=None
                 ):
        super().__init__(parent)

        self._stack = QtWidgets.QStackedLayout(self)

        # self._stack.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        self._stack.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackOne)

        self._gradients: list[GradientOverlayWidget] = []
        self._splines: list[SplineOverlayWidget] = []
        self._names: list[str] = []
        self._active_idx = -1

        self.add_overlay(gradient, spline)
        self.set_active_layer(0)

    # --- public API (kept compatible via properties) -------------------------

    @property
    def gradient(self):
        # active gradient
        return self._gradients[self._active_idx]

    @property
    def spline(self):
        # active spline
        return self._splines[self._active_idx]

    def get_active_idx(self):
        return self._active_idx

    # --- naming helpers ------------------------------------------------

    def set_layer_name(self, index: int, name: str) -> None:
        """Set the display name for a layer and notify listeners."""
        if 0 <= index < len(self._names):
            nm = name if isinstance(name, str) else ""
            if self._names[index] != nm:
                self._names[index] = nm
                self.layerNameChanged.emit(index)

    def layer_name_at(self, index: int) -> str | None:
        """Return the display name for a layer, or None if out of range."""
        if 0 <= index < len(self._names):
            return self._names[index]
        return None

    # --- new helpers for multi-overlay management ----------------------------

    def add_overlay(self,
                    gradient: GradientOverlayWidget | None = None,
                    spline: SplineOverlayWidget | None = None) -> int:
        # grad = gradient or GradientOverlayWidget(HsvWheelGradient(300, 300, 298))
        grad = gradient or GradientOverlayWidget(HsvSquareGradient(300, 300, 298, hue=0))
        spl = spline or SplineOverlayWidget(grad)

        # each overlay is a small stacked container of gradient + spline
        container = QtWidgets.QWidget(self)
        lay = QtWidgets.QStackedLayout(container)
        lay.setStackingMode(QtWidgets.QStackedLayout.StackingMode.StackAll)
        lay.addWidget(grad)
        lay.addWidget(spl)

        idx = len(self._gradients)
        self._gradients.append(grad)
        self._splines.append(spl)
        self._names.append(f"Layer {idx + 1}")
        self._stack.addWidget(container)

        # re-emit spline updates as overlayUpdated(idx)
        sig = spl.pointsChanged
        if sig is not None:
            try:
                sig.connect(lambda i=idx: self.overlayUpdated.emit(i))
            except Exception:
                pass

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

    def spline_at(self, index: int) -> SplineOverlayWidget | None:
        if 0 <= index < len(self._splines):
            return self._splines[index]
        return None

    def __getitem__(self, key):
        """Allow overlay['Layer 1'] or overlay[0] access."""
        if isinstance(key, int):
            if 0 <= key < len(self._gradients):
                return type("OverlayEntry", (), {
                    "gradient": self._gradients[key],
                    "spline": self._splines[key],
                    "name": self._names[key],
                })()
            raise IndexError(key)
        if isinstance(key, str):
            try:
                idx = self._names.index(key)
            except ValueError:
                raise KeyError(key)
            return self[idx]
        raise TypeError("key must be int or str")

    def __len__(self):
        return len(self._gradients)