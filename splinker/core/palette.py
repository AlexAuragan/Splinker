from copy import deepcopy
from dataclasses import asdict

from splinker.core import Layer, Point


class Palette:
    def __init__(self, name: str = None, layers: list[Layer] = None, active_idx: int = -1):
        self._layers = layers or []
        self._name = name
        self._active_idx = active_idx if 0 <= active_idx < len(self._layers) else (0 if self._layers else -1)



    @property
    def name(self):
        return self._name

    @property
    def active_idx(self) -> int:
        return self._active_idx

    @property
    def active_layer(self) -> Layer:
        if self._active_idx < 0 or self._active_idx >= len(self._layers):
            raise IndexError("No active layer")
        return self._layers[self._active_idx]

    def __len__(self) -> int:
        return len(self._layers)

    def __getitem__(self, key: int | str) -> Layer:
        if isinstance(key, int):
            if 0 <= key < len(self._layers):
                return self._layers[key]
            raise IndexError(key)
        if isinstance(key, str):
            for layer in self._layers:
                if layer.name == key:
                    return layer
            raise KeyError(key)
        raise TypeError("key must be int or str")

    def set_name(self, name: str) -> None:
        self._name = name

    def set_layer_name(self, index: int, name: str) -> None:
        if not (0 <= index < len(self._layers)):
            raise IndexError(index)
        self._layers[index].name = name if isinstance(name, str) else ""

    def set_active(self, index: int) -> None:
        if not (0 <= index < len(self._layers)):
            raise IndexError(index)
        self._active_idx = index

    def add_layer(self, layer: Layer) -> int:
        idx = len(self._layers)
        self._layers.append(layer)
        if self._active_idx == -1:
            self._active_idx = 0
        return idx

    def remove_layer(self, index: int) -> bool:
        if not (0 <= index < len(self._layers)):
            return False
        self._layers.pop(index)
        if len(self._layers) == 0:
            self._active_idx = -1
        elif self._active_idx >= len(self._layers):
            self._active_idx = len(self._layers) - 1
        return True

    def duplicate_layer(self, index: int) -> int:
        if not (0 <= index < len(self._layers)):
            raise IndexError(index)
        original = self._layers[index]
        new_layer = Layer(
            gradient=original.gradient,
            path=deepcopy(original.path),
            name=f"{original.name} Copy" if original.name else "Layer Copy",
        )
        return self.add_layer(new_layer)

    def to_dict(self) -> dict:
        """
        Returns a JSON-serializable dict if your Layer, Path, Gradient dataclasses
        implement dataclass fields or provide their own to_dict methods.
        Adjust as needed for your core classes.
        """

        return {
            "name": self._name,
            "active_idx": self._active_idx,
            "layers": [l.to_dict() for l in self._layers],
        }

    @classmethod
    def from_dict(cls, data: dict, layer_factory) -> "Palette":
        """
        layer_factory: callable that takes a layer dict and returns a Layer object.
        """
        layers = [layer_factory(ld) for ld in data.get("layers", [])]
        return cls(
            name=data.get("name"),
            layers=layers,
            active_idx=data.get("active_idx", -1),
        )

    def contains_point(self, point: Point):
        return self.active_layer.gradient.contains_point(point[0], point[1])

