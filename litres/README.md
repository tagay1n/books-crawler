# Litres

Litres uses the root unified CLI. See [configuration, command replacements,
migration and recovery](../docs/ingestion/litres.md).

Provider parsing and conversion components remain in this directory; the old
`litres/cli.py` entry point has been removed. Operational settings, including SID,
come from `sources.litres` in the explicitly selected `--config` YAML.
