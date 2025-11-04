from PySide6 import QtCore, QtWidgets
from typing import Callable
from splinker.core.gradients import Gradient, HsvWheelGradient, HsvSquareGradient

EditorFactory = Callable[[], "IGradientEditor"]

class IGradientEditor(QtWidgets.QWidget):
    gradientChanged = QtCore.Signal(object)  # emits a core.Gradient

    def __init__(self, parent=None):
        super().__init__(parent)
        self._throttle_ms = 300
        self._emit_timer = QtCore.QTimer(self)
        self._emit_timer.setSingleShot(True)
        self._emit_timer.timeout.connect(self._emit_now)
        self._leading_lock = False     # optional "leading edge" behavior

    # --- public API kept -----------------------------------------------------
    def setGradient(self, grad: Gradient | None) -> None: ...
    def gradient(self) -> Gradient | None: ...

    # --- throttle controls (optional to call) --------------------------------
    def setThrottleMs(self, ms: int) -> None:
        """Set debounce delay in milliseconds (0 = no throttle)."""
        self._throttle_ms = max(0, int(ms))

    def setLeadingEmit(self, enabled: bool) -> None:
        """
        If enabled, emit immediately on first change, then suppress until
        the debounce window elapses (leading-edge debounce).
        """
        self._leading_lock = bool(enabled)

    # --- internal emit helpers ----------------------------------------------
    def _emit_now(self) -> None:
        g = self.gradient()
        if g is not None:
            self.gradientChanged.emit(g)
        # release the leading lock at the end of the window
        if self._leading_lock:
            # stop ensures the window ends right here if timer was already inactive
            self._emit_timer.stop()

    @QtCore.Slot()
    def _emit_changed(self) -> None:
        """
        Call this from valueChanged signals in subclasses.
        Debounces gradientChanged according to _throttle_ms.
        """
        if self._throttle_ms <= 0:
            self._emit_now()
            return

        if self._leading_lock and not self._emit_timer.isActive():
            # Leading-edge: fire immediately, then open the window
            self._emit_now()
            self._emit_timer.start(self._throttle_ms)
            return

        # Trailing-edge: coalesce and emit once after quiet period
        self._emit_timer.start(self._throttle_ms)




class HsvWheelEditor(IGradientEditor):
    """
    Editor for HsvWheelGradient.
    Editable: value [0..255], alpha [0..255]
    Non-editable (tracked from incoming gradient): cx, cy, radius
    """
    gradientChanged = QtCore.Signal(object)  # emits HsvWheelGradient

    def __init__(self,parent=None):
        super().__init__(parent)

        # Stored geometry (non-editable here)
        self._cx: float = 0.0
        self._cy: float = 0.0
        self._radius: float = 0.0

        # Controls
        self._value = QtWidgets.QSpinBox()
        self._value.setRange(0, 255)
        self._value.setSuffix("  (V)")
        self._alpha = QtWidgets.QSpinBox()
        self._alpha.setRange(0, 255)
        self._alpha.setSuffix("  (A)")

        # Layout (compact)
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Value", self._value)
        # form.addRow("Alpha", self._alpha)

        # Wiring
        self._value.valueChanged.connect(self._emit_changed)
        self._alpha.valueChanged.connect(self._emit_changed)

    # --- Public API

    def setGradient(self, grad: Gradient | None) -> None:
        """
        Accepts an HsvWheelGradient; ignores other types.
        Updates geometry (cx, cy, radius) and editable fields.
        """
        if not isinstance(grad, HsvWheelGradient):
            return

        # Update geometry we mirror but don't expose for editing
        self._cx = float(grad.cx)
        self._cy = float(grad.cy)
        self._radius = float(grad.radius)

        # Update editable controls without triggering emissions
        try:
            self.blockSignals(True)
            self._value.setValue(int(grad.value))
            self._alpha.setValue(int(grad.alpha))
        finally:
            self.blockSignals(False)

        # Emit a normalized instance (useful if host wants immediate echo)
        self._emit_changed()

    def gradient(self) -> HsvWheelGradient | None:
        """
        Build a fresh gradient using stored geometry + current controls.
        """
        if self._radius <= 0.0:
            # Cannot represent a valid wheel without a positive radius
            return None
        return HsvWheelGradient(
            self._cx, self._cy, self._radius,
            value=int(self._value.value()),
            alpha=int(self._alpha.value()),
        )


class HsvSquareEditor(IGradientEditor):
    """
    Editor for HsvSquareGradient.
    Editable: hue [0..359], alpha [0..255]
    Non-editable (tracked from incoming gradient): cx, cy, size
    """
    gradientChanged = QtCore.Signal(object)  # emits HsvSquareGradient

    def __init__(self, parent=None):
        super().__init__(parent)

        # Stored geometry (non-editable here)
        self._cx: float = 0.0
        self._cy: float = 0.0
        self._size: float = 0.0

        # Controls
        self._hue = QtWidgets.QSpinBox()
        self._hue.setRange(0, 359)
        self._hue.setSuffix("°")
        self._alpha = QtWidgets.QSpinBox()
        self._alpha.setRange(0, 255)
        self._alpha.setSuffix("  (A)")

        # Layout (compact)
        form = QtWidgets.QFormLayout(self)
        form.setContentsMargins(0, 0, 0, 0)
        form.addRow("Hue", self._hue)
        # form.addRow("Alpha", self._alpha)

        # Wiring
        self._hue.valueChanged.connect(self._emit_changed)
        self._alpha.valueChanged.connect(self._emit_changed)

    # --- Public API

    def setGradient(self, grad: Gradient | None) -> None:
        """
        Accepts an HsvSquareGradient; ignores other types.
        Updates geometry (cx, cy, size) and editable fields.
        """
        if not isinstance(grad, HsvSquareGradient):
            return

        # Update geometry we mirror but don't expose
        self._cx = float(grad.cx)
        self._cy = float(grad.cy)
        self._size = float(grad.S)

        # Update editable controls without triggering emissions
        try:
            self.blockSignals(True)
            self._hue.setValue(int(grad.hue if grad.hue >= 0 else 0))
            self._alpha.setValue(int(grad.alpha))
        finally:
            self.blockSignals(False)

        # Emit a normalized instance (useful if host wants immediate echo)
        self._emit_changed()

    def gradient(self) -> HsvSquareGradient | None:
        """
        Build a fresh gradient using stored geometry + current controls.
        """
        if self._size <= 0.0:
            # Cannot represent a valid square without positive size
            return None
        return HsvSquareGradient(
            self._cx, self._cy, self._size,
            hue=int(self._hue.value()),
            alpha=int(self._alpha.value()),
        )


