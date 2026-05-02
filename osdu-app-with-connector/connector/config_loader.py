"""Load :class:`ConnectorRuntimeConfig` from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from connector.models.config import ConnectorRuntimeConfig


def load_runtime_config(path: Union[str, Path]) -> ConnectorRuntimeConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("runtime YAML must be a mapping")
    return ConnectorRuntimeConfig.model_validate(raw)
