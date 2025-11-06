from typing import Type

from .editors import EditorFactory, HsvWheelEditor, HsvSquareEditor
from .canvas import CanvasWidget
from splinker.core.gradients import Gradient, HsvWheelGradient, HsvSquareGradient
from splinker.widgets.layer_display import PaletteDisplayComponent

editor_registry: dict[Type[Gradient], EditorFactory] = {
    HsvWheelGradient:  lambda: HsvWheelEditor(),
    HsvSquareGradient: lambda: HsvSquareEditor(),
}
__all__ = [
    "CanvasWidget",
    "editor_registry",
    "PaletteDisplayComponent"
]
