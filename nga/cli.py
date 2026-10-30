"""`nga` -- one entry point per stage. Each command is one non-interactive Orchestra task."""

from __future__ import annotations

import os
import subprocess
import sys
from enum import Enum
from pathlib import Path

import typer

from nga import generate as generate_stage
from nga.config import DBT_DIR, ROOT, SOURCE_DUCKDB, ConfigError, settings

app = typer.Typer(
    help="model2data + public APIs -> dlt -> MotherDuck -> dbt, stage by stage.",
    no_args_is_help=True,
    context_settings={"help_option_names": ["-h", "--help"]},
)


class Source(str, Enum):
    shop = "shop"
    weather = "weather"
    fx = "fx"
    holidays = "holidays"
    all = "all"


def _fail(message: str, code: int = 1) -> typer.Exit:
    typer.secho(message, fg=typer.colors.RED, err=True)
    return typer.Exit(code)


def _settings():
    try:
        return settings()
    except ConfigError as exc:
        raise _fail(f"Configuration error: {exc}") from exc


def _dbt_env() -> dict[str, str]:
    """Environment for the dbt child process.

    The interpreter running this CLI owns the right dbt; without putting its bin directory
    first, a bare `dbt` resolves through whatever shim happens to be on PATH and fails or --
    worse -- silently uses a different version. The warehouse settings are passed explicitly so
    dbt reaches the same warehouse dlt just wrote.
    """
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(Path(sys.executable).parent), env.get("PATH", "")])
    env["DBT_PROFILES_DIR"] = str(DBT_DIR)
    env.update(_settings().subprocess_env())
    return env


def _run_dbt(args: list[str]) -> None:
    """Run dbt in dbt/, surfacing its own output and exit code instead of a traceback."""
    _run_tool("dbt", [*args, "--profiles-dir", str(DBT_DIR)])


def _run_tool(tool: str, args: list[str]) -> None:
    """Run dbt or MetricFlow's `mf` in dbt/ against the same warehouse, passing the exit code on.

    `mf` reads the dbt profile from DBT_PROFILES_DIR (set by `_dbt_env`) and needs the project
    directory as cwd. It does not parse the project: it reads target/semantic_manifest.json as the
    last dbt command left it, which names tables in that run's warehouse. So `mf` is preceded by a
    `dbt parse` against the same environment, or a query aims at the wrong database.
    """
    if not (DBT_DIR / "dbt_project.yml").exists():
        raise _fail(
            f"No dbt project at {DBT_DIR} (dbt_project.yml is missing). "
            "The transform stage needs the dbt project; run `nga load` on its own until it exists."
        )
    if tool == "mf":
        _parse_dbt()
    cmd = [tool, *args]
    typer.secho("$ " + " ".join(cmd), fg=typer.colors.BLUE)
    result = subprocess.run(cmd, cwd=DBT_DIR, env=_dbt_env(), check=False)
    if result.returncode != 0:
        raise typer.Exit(result.returncode)


def _parse_dbt() -> None:
    """Refresh target/semantic_manifest.json for the current environment (see `_run_tool`)."""
    result = subprocess.run(
        ["dbt", "parse", "--quiet", "--profiles-dir", str(DBT_DIR)],
        cwd=DBT_DIR,
        env=_dbt_env(),
        check=False,
    )
    if result.returncode != 0:
        raise _fail("dbt parse failed; fix the dbt project before querying metrics.")


@app.command()
def generate() -> None:
    """Stage 1 -- generate the synthetic Noordkust source system (model2data) as DuckDB."""
    generate_stage.generate()
    typer.secho("Source system ready.", fg=typer.colors.GREEN)


def _load_one(name: str) -> None:
    from dlt.pipeline.exceptions import PipelineStepFailed

    from nga.pipelines import fx, holidays, shop, weather

    module = {"shop": shop, "weather": weather, "fx": fx, "holidays": holidays}[name]
    typer.secho(f"Loading {name}...", fg=typer.colors.BLUE)
    try:
        info = module.run(_settings())
    except PipelineStepFailed as exc:
        # dlt keeps a failed package and retries it on the next run, which silently ignores
        # any new data. Say so here rather than letting the next run look like a no-op.
        pipeline = exc.pipeline.pipeline_name
        typer.secho(f"dlt failed during {exc.step}: {exc.exception}", fg=typer.colors.RED, err=True)
        typer.secho(
            f"The load package is still pending. Inspect it with `dlt pipeline {pipeline} info`, "
            f"then retry `nga load {name}` or discard it with "
            f"`dlt pipeline {pipeline} drop-pending-packages`.",
            err=True,
        )
        raise typer.Exit(1) from exc
    typer.echo(info)


@app.command()
def load(
    source: Source = typer.Argument(Source.all, help="Which source to load."),
) -> None:
    """Stage 2 -- extract into the warehouse with dlt (merge, so re-running is safe)."""
    names = ["shop", "weather", "fx", "holidays"] if source is Source.all else [source.value]
    for name in names:
        _load_one(name)
    typer.secho("Raw data loaded.", fg=typer.colors.GREEN)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def transform(ctx: typer.Context) -> None:
    """Stage 3 -- run dbt in dbt/ (default `dbt build`; extra args go to dbt as given)."""
    args = ctx.args
    cmd = ["build", *args] if not args or args[0].startswith("-") else args
    _run_dbt(cmd)
    typer.secho("Transformations done.", fg=typer.colors.GREEN)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def metrics(ctx: typer.Context) -> None:
    """Query the MetricFlow metrics defined in dbt/ (`mf` with the right cwd and environment).

    Examples: `nga metrics list`, `nga metrics validate-configs`,
    `nga metrics query --metrics realised_revenue_eur --group-by metric_time__month`.
    """
    _run_tool("mf", ctx.args)


@app.command("dashboard-sql")
def dashboard_sql() -> None:
    """Compile the KPI dashboard's queries with MetricFlow into dashboard/queries/*.sql."""
    from nga import dashboard

    _parse_dbt()
    try:
        files = dashboard.export(_dbt_env())
    except subprocess.CalledProcessError as exc:
        # mf reports query errors on stdout
        out = (exc.stdout or b"") + (exc.stderr or b"")
        detail = [ln for ln in out.decode(errors="replace").splitlines() if "Error" in ln][-5:]
        raise _fail("MetricFlow query failed:\n" + "\n".join(detail)) from exc
    for f in files:
        typer.echo(f"wrote {f.relative_to(ROOT)}")


@app.command()
def run(
    skip_generate: bool = typer.Option(False, help="Reuse the existing generated source system."),
) -> None:
    """Run every stage in order: generate (if needed) -> load all -> dbt build."""
    if not skip_generate and not SOURCE_DUCKDB.exists():
        generate_stage.generate()
    load(Source.all)
    _run_dbt(["build"])
    typer.secho(
        f"Full run complete (destination: {_settings().destination}).", fg=typer.colors.GREEN
    )


if __name__ == "__main__":
    app()
