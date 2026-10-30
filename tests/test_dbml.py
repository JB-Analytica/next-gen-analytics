"""The DBML is the contract for the whole stack: guard the things downstream relies on."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import pytest

from nga.config import SOURCE_DBML
from nga.generate import BusinessShape, _generated_project_env
from nga.pipelines.shop import TABLES

BIN = Path(sys.executable).parent


@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("m2d")
    subprocess.run(
        [
            str(BIN / "model2data"),
            "--file",
            str(SOURCE_DBML),
            "--name",
            "t",
            "--rows",
            "12",
            "--seed",
            "1",
            "--as-of",
            "2026-01-01",
            "--force",
        ],
        cwd=out,
        check=True,
        capture_output=True,
    )
    return out / "dbt_t" / "seeds" / "raw"


# Columns align_source sets after generation. model2data suggests a cross-table "after" for them,
# but that hint picks the earliest parents for most children, so these warnings are expected.
ALIGNED_COLUMNS = (
    "tables.order_items.columns.created_at:",
    "tables.returns.columns.created_at:",
)


def test_dbml_validates_without_unexpected_warnings() -> None:
    result = subprocess.run(
        [str(BIN / "model2data"), "validate", str(SOURCE_DBML)],
        check=True,
        capture_output=True,
        text=True,
    )
    lines = (result.stdout + result.stderr).splitlines()
    unexpected = [
        line
        for line in lines
        if line.strip().startswith("- ") and not line.strip()[2:].startswith(ALIGNED_COLUMNS)
    ]
    assert unexpected == []
    assert "conforms to spec" in result.stdout + result.stderr


def test_every_extracted_table_is_generated(generated: Path) -> None:
    for table in TABLES:
        assert (generated / f"{table}.csv").exists(), table


def test_cursor_columns_exist(generated: Path) -> None:
    for table, cursor in TABLES.items():
        with open(generated / f"{table}.csv", newline="") as f:
            header = next(csv.reader(f))
        assert cursor in header, f"{table} has no {cursor} column for dlt to page on"
        assert "id" in header, f"{table} has no id column for dlt to merge on"


def test_align_source_placeholders_exist(generated: Path) -> None:
    """align_source writes these columns by name; losing one in the DBML would break it."""
    with open(generated / "orders.csv", newline="") as f:
        orders = next(csv.reader(f))
    for column in (
        "currency",
        "subtotal_minor",
        "shipping_minor",
        "total_minor",
        "shipping_country",
    ):
        assert column in orders
    with open(generated / "order_items.csv", newline="") as f:
        items = next(csv.reader(f))
    assert {"unit_price_minor", "discount_minor"} <= set(items)


def test_generated_project_env_drops_our_dbt_vars(monkeypatch: pytest.MonkeyPatch) -> None:
    """dbt reads DBT_TARGET from the environment, so leaking this repo's value into the
    generated project's build would fail it: it has a `dev` target only."""
    monkeypatch.setenv("DBT_TARGET", "prod")
    monkeypatch.setenv("DBT_PROFILES_DIR", "/somewhere/else")
    monkeypatch.setenv("GCP_PROJECT", "example-project")

    env = _generated_project_env()

    assert "DBT_TARGET" not in env
    assert "DBT_PROFILES_DIR" not in env
    assert env["GCP_PROJECT"] == "example-project", "unrelated variables must still pass through"
    assert env["PATH"].startswith(str(BIN))


def test_as_of_is_pinned_and_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NGA_AS_OF", raising=False)
    assert BusinessShape().as_of == "2026-10-01"
    monkeypatch.setenv("NGA_AS_OF", "2026-12-31")
    assert BusinessShape().as_of == "2026-12-31"
    args = BusinessShape().cli_args()
    assert args[args.index("--as-of") + 1] == "2026-12-31"
    assert "--seed" in args and args[args.index("--seed") + 1] == "42"
