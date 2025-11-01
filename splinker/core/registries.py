from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from .gradients import Gradient
    from .point_editors import PointEditorComponent

point_editor_registry: dict[str, type["PointEditorComponent"]] = {}
gradient_registry: dict[str, type["Gradient"]] = {}


def register_point_editor(name: str):
    def _decorator(cls: type["PointEditorComponent"]) -> type["PointEditorComponent"]:
        if not name or name in point_editor_registry:
            raise ValueError(f"Invalid or duplicate point editor name '{name}'")
        point_editor_registry[name] = cls
        return cls
    return _decorator

def register_gradient(name: str):
    def _decorator(cls: type["Gradient"]) -> type["Gradient"]:
        if not name or name in gradient_registry:
            raise ValueError(f"Invalid or duplicate spline name '{name}'")
        gradient_registry[name] = cls
        return cls
    return _decorator