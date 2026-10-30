# Noordkust KPI dashboard

The dashboard is a Claude Dashboard artifact, private to its owner's Claude account; `artifact/`
holds everything needed to recreate it in your own. It queries MotherDuck live through Claude's MotherDuck connector, so every viewer needs read
access to `next_gen_analytics`. It is private until shared from its Share menu.

| Path | What it is |
|---|---|
| `queries/<id>.sql` | the SQL each chart runs, compiled by MetricFlow (`nga dashboard-sql`) |
| `artifact/meta.json` | the dashboard's title |
| `artifact/datasets/<id>.json` | each chart's data source: title, description and its live query |
| `artifact/index.html` | the page: layout, charts, the loader for MotherDuck's answer |

`artifact/` is a backup of what the dashboard holds, so its history is tracked here.
`tests/test_dashboard.py` checks that each backed-up query is exactly its `queries/<id>.sql`.

## Keeping the backup current

The dashboard is changed through Claude, not by editing these files. After any change, ask
Claude to export the dashboard into `dashboard/artifact/`: it reads the dashboard's `dash`,
`datasets` and `files` documents and writes them here in this layout. Commit the diff.

## Changing a metric the dashboard uses

1. Edit the dbt YAML, then run `DBT_TARGET=prod uv run nga dashboard-sql`.
2. Ask Claude to set each changed `queries/<id>.sql` as that dataset's query in the dashboard,
   unchanged, and to refresh the backup.
3. Commit the SQL and the backup together.

## Restoring

Ask Claude to recreate the dashboard from `artifact/`. A new Dashboard artifact is filled with
`dash/meta` from `meta.json`, one `datasets/<id>` per file in `datasets/`, and `files/index.html`
as `{"text": <index.html>}`. The `formerFile` entries point at old snapshot files inside the
original artifact; a new one does not need them.
