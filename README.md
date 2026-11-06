# Books Crawler

Discover and acquire documents through source adapters with shared PostgreSQL progress storage.
Original and derived documents remain in local artifact directories.

## Setup

1. Create a virtual environment: `python -m venv .venv`.
2. Install dependencies: `.venv/bin/pip install -r requirements.txt`.
3. Review `config/sources/<source>.yaml` and `config/defaults.yaml`; supply the environment variables required by your source and publication target. See [configuration](docs/ingestion/operations.md).
4. Follow [PostgreSQL setup and legacy import](docs/postgres-migration.md).

## Common commands

```bash
.venv/bin/python cli.py sources
.venv/bin/python cli.py --summary-only --config config/sources/magarif.yaml status --source magarif
.venv/bin/python scripts/ingestion_overview.py --database --source magarif
```

`run` discovers, acquires and publishes completed documents to configured S3 storage.
`download` and `finalize` are local stages. Source capabilities and admission rules vary;
consult the [source guides](docs/local-ingestion.md) before running ingestion.
Local JSON manifests are archived snapshots or explicit exports, not active progress state.

- [Documentation map](docs/README.md)
- [Adapter development and agent workflows](docs/adapter-development.md)
- [Configuration, budgets and recovery](docs/ingestion/operations.md)
- [Bounded public-page inspection](docs/source-inspection.md)
- [Discovery review register](docs/source-discovery-reviews.md)
