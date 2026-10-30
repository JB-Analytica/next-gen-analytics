from __future__ import annotations

import pytest
from typer.testing import CliRunner

from nga import cli
from nga.cli import app


def test_help_lists_every_stage() -> None:
    result = CliRunner().invoke(app, ["--help"])
    assert result.exit_code == 0
    for stage in ("generate", "load", "transform", "run"):
        assert stage in result.output


def test_load_without_a_token_fails_with_a_message(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("NGA_DESTINATION", raising=False)
    monkeypatch.delenv("MOTHERDUCK_TOKEN", raising=False)
    result = CliRunner().invoke(app, ["load", "weather"])
    assert result.exit_code == 1
    assert "MOTHERDUCK_TOKEN" in result.output


def test_transform_without_a_dbt_project_fails_clearly(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr(cli, "DBT_DIR", tmp_path / "dbt")
    result = CliRunner().invoke(app, ["transform"])
    assert result.exit_code == 1
    assert "No dbt project" in result.output


def test_transform_passes_extra_args_through(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / "dbt").mkdir()
    (tmp_path / "dbt" / "dbt_project.yml").write_text("name: x\n")
    monkeypatch.setattr(cli, "DBT_DIR", tmp_path / "dbt")
    monkeypatch.setenv("NGA_DESTINATION", "duckdb")
    calls = []

    class Done:
        returncode = 0

    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: calls.append((cmd, kw)) or Done())
    runner = CliRunner()
    assert runner.invoke(app, ["transform", "--select", "+fct_orders"]).exit_code == 0
    assert runner.invoke(app, ["transform", "test", "-s", "stg_orders"]).exit_code == 0
    assert calls[0][0][:4] == ["dbt", "build", "--select", "+fct_orders"]
    assert calls[1][0][:4] == ["dbt", "test", "-s", "stg_orders"]
    assert calls[0][0][-2:] == ["--profiles-dir", str(tmp_path / "dbt")]
    assert calls[0][1]["cwd"] == tmp_path / "dbt"
    assert calls[0][1]["env"]["NGA_DESTINATION"] == "duckdb"


def test_transform_surfaces_dbt_exit_code(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    (tmp_path / "dbt").mkdir()
    (tmp_path / "dbt" / "dbt_project.yml").write_text("name: x\n")
    monkeypatch.setattr(cli, "DBT_DIR", tmp_path / "dbt")
    monkeypatch.setenv("NGA_DESTINATION", "duckdb")

    class Failed:
        returncode = 2

    monkeypatch.setattr(cli.subprocess, "run", lambda cmd, **kw: Failed())
    assert CliRunner().invoke(app, ["transform"]).exit_code == 2
