"""Dict-like wrapper: runtime overlay + managed payments/integrations win over YAML."""
from __future__ import annotations

from typing import Any, Iterator, Mapping

from common_db.runtime_config.overlay import (
    apply_integrations_to_mapping,
    apply_payments_to_mapping,
    get_overlay,
)
from common_db.runtime_config.keys import RUNTIME_KEYS


class DualSourceConfig(Mapping[str, Any]):
    """Read-through view of YAML with DB overlay.

    Mutations (``__setitem__``) write to the underlying YAML dict — used by the
    bot's in-memory admin config_manager. Overlay values still win on read for
    RUNTIME_KEYS / managed payments / managed integrations.
    """

    def __init__(self, yaml_config: dict[str, Any]):
        self._yaml = yaml_config

    def _merged(self) -> dict[str, Any]:
        merged = dict(self._yaml)
        overlay = get_overlay()
        for key, value in overlay.items():
            if key == "maintenance":
                continue
            if key in RUNTIME_KEYS:
                merged[key] = value
        merged = apply_payments_to_mapping(merged)
        return apply_integrations_to_mapping(merged)

    def get(self, key: str, default: Any = None) -> Any:
        return self._merged().get(key, default)

    def __getitem__(self, key: str) -> Any:
        merged = self._merged()
        return merged[key]

    def __setitem__(self, key: str, value: Any) -> None:
        self._yaml[key] = value

    def __contains__(self, key: object) -> bool:
        return key in self._merged()

    def __iter__(self) -> Iterator[str]:
        return iter(self._merged())

    def __len__(self) -> int:
        return len(self._merged())

    def keys(self):
        return self._merged().keys()

    def values(self):
        return self._merged().values()

    def items(self):
        return self._merged().items()

    def yaml_dict(self) -> dict[str, Any]:
        return self._yaml

    def copy(self) -> dict[str, Any]:
        return dict(self._merged())
