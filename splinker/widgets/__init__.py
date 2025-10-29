from typing import Type

from .editors import EditorFactory, HsvWheelEditor, HsvSquareEditor
from .overlay import Overlay
from splinker.core.gradients import Gradient, HsvWheelGradient, HsvSquareGradient

editor_registry: dict[Type[Gradient], EditorFactory] = {
    HsvWheelGradient:  lambda: HsvWheelEditor(),
    HsvSquareGradient: lambda: HsvSquareEditor(),
}
__all__ = [
    "Overlay",
    "editor_registry"
]
