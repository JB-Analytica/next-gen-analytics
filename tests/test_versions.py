"""dbt/requirements.txt (read by Orchestra's dbt Core task) must match the uv lock."""

from __future__ import annotations

import importlib.metadata as metadata

from nga.config import DBT_DIR


def test_dbt_requirements_match_the_lock() -> None:
    pins = {}
    for line in (DBT_DIR / "requirements.txt").read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            name, version = line.split("==")
            pins[name] = version
    assert pins, "dbt/requirements.txt pins nothing"
    for name, version in pins.items():
        assert metadata.version(name) == version, name
