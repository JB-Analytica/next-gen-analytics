# Running the stack in Orchestra

Orchestra clones this repository on every task run and executes one command per task on its
own compute. Every stage of the `nga` CLI is shaped for that: non-interactive, logs to stdout,
non-zero exit on failure, and `load shop` regenerates the synthetic source from a clean clone.

## What you need first

- An Orchestra account (the free **Lean** tier is enough: 1 user, 1 environment,
  100 compute minutes a day for dbt and Python).
- A MotherDuck account and a **read/write** token for the loader and dbt
  (Settings → Access tokens, or a service account). The database `next_gen_analytics` is
  created on the first load.
- Orchestra's GitHub connection with access to `JB-Analytica/next-gen-analytics`
  (Settings → Integrations → GitHub; each Orchestra workspace connects separately).

## 1. Connections

**Python** connection (used by the four load tasks):

| Field | Value |
|---|---|
| Repository | `JB-Analytica/next-gen-analytics`, via the workspace Git connection |
| Package manager | `UV` |
| Python version | `3.12` |
| Secret JSON | `{"MOTHERDUCK_TOKEN": "<token>"}` |

**dbt Core** connection (used by the transform task):

| Field | Value |
|---|---|
| Repository | `JB-Analytica/next-gen-analytics` |
| Profiles | upload `dbt/profiles.yml` from this repo unchanged; it reads everything from the environment |
| Secret JSON | `{"MOTHERDUCK_TOKEN": "<token>"}` |

Skip **Validate** on the dbt connection: Orchestra documents false negatives for MotherDuck
profiles and requires the dbt project at the repository root, which this one is not.

## 2. The pipeline

Build it in the UI with **Git Control** on, file path `orchestra/pipeline.yml`, working branch
`orchestra_dev`. Orchestra then commits the pipeline YAML to this repo and keeps it in sync, so
the pipeline is reviewed like any other change. (Do not create that file by hand first: Orchestra
refuses a path that already exists.)

```
ingest  (parallel)                         transform  (depends on ingest)
├─ load_shop      uv run nga load shop     └─ dbt_build   dbt build --target prod
├─ load_weather   uv run nga load weather                   project dir: dbt
├─ load_fx        uv run nga load fx                        state orchestration: on
└─ load_holidays  uv run nga load holidays
```

- **Python tasks** (`PYTHON_EXECUTE_SCRIPT`): build command `uv sync --frozen --no-dev`,
  command as above, environment variables `{"NGA_DESTINATION": "motherduck"}`.
- **dbt Core task** (`DBT_CORE_EXECUTE`): project dir `dbt`, command `dbt build --target prod`,
  environment variables `{"NGA_DESTINATION": "motherduck", "DBT_TARGET": "prod",
  "ORCHESTRA_SEND_WARNING": "true"}`, **Use state orchestration** on. The dbt sources carry
  freshness derived from dlt's load id and the marts carry `build_after`, which is what state-aware
  runs read.
- **Schedule**: daily, for example `0 6 * * ? *` in `Europe/Brussels`.

The four loads write to different MotherDuck schemas, so running them in parallel is safe (the
single-writer lock only applies to the local DuckDB file).

## 3. What to look at once it runs

- **State-aware skipping.** The synthetic shop is pinned to `NGA_AS_OF` (2026-10-01), so after the
  first run nothing changes upstream and the next scheduled run should skip most models.
  That is the feature at work, not a broken pipeline. Set `NGA_AS_OF` to a later date on the
  `load_shop` task, or wait for new weather and FX days, to watch it rebuild only what changed.
- **Lineage and assets.** Orchestra reads dbt's artifacts to draw lineage from the raw schemas
  to the marts.
- **Compute minutes.** Each Python task spends most of its time in `uv sync`. Keep an eye on the
  daily total against the 100-minute free allowance.

## Fallback

If the dbt Core task cannot resolve dependencies, run dbt as a fifth Python task instead:
`uv run nga transform build --target prod`. You lose state-aware orchestration, which only
exists on the dbt Core task.
