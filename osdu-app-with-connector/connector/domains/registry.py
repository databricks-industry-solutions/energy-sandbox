"""Load :class:`DomainConfig` from YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import Union

import yaml

from connector.models.config import DomainConfig


def load_domain_config(path: Union[str, Path]) -> DomainConfig:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError(f"domain YAML must be a mapping: {path}")
    return DomainConfig.model_validate(raw)


def load_domains_from_dir(directory: Union[str, Path]) -> dict[str, DomainConfig]:
    out: dict[str, DomainConfig] = {}
    d = Path(directory)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.yaml")):
        cfg = load_domain_config(p)
        out[cfg.name] = cfg
    return out
