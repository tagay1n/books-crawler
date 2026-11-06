# Adapter interface

Start with [the development map](adapter-development.md) for navigation and
[implementation contracts](ingestion-architecture.md) for stage/checkpoint rules.
Adapters are modules or configured `CollectionAdapter` instances. No base class
is required. Static capabilities and source/module mappings belong to
`registry.DESCRIPTORS`; `SOURCES[source]` lazily imports the implementation.
`cli.py sources --details --source NAME` reports capabilities and repository paths.
Helper paths follow the adapter's filename prefix, excluding other adapters;
shared utilities are listed in the development map.

## Shared discovery and acquisition

| Member | Contract |
| --- | --- |
| `PARSER_VERSION` | Integer observation/parser version; defaults to 1 |
| `record(html, page_url)` | Return `(metadata, assets)`; metadata includes `url` and `title` |
| `parse_listing(html, request, root)` | Return `paging.ListingPage`; required by shared discovery |
| `UNIQUE_RECORDS` | Optional flag requiring globally unique catalog record URLs |
| `initial_request(root)` | Optional initial `PageRequest`; defaults to GET of root |
| `verification_request(root, advertised)` | Optional final listing verification request |
| `record_key(metadata)` | Optional stable identity; defaults to metadata URL |
| `resolve_record(http, metadata, assets)` | Optional qualification/enrichment; returns updated pair |
| `prepare_http(http, session_file)` | Optional request/redirect guards and provider hooks |
| `download(http, manifest, summary, log, recheck, *, selected_records=None)` | Optional acquisition override; defaults to shared file downloader, or image-issue downloader for `DOWNLOAD_UNIT = "issue"` |
| `finalize(settings, budget, manifest, summary, log, *, selected_records=None)` | Optional local-only assembly stage |

`selected_records` is an invocation-local **output collector**, not a download
filter. A staged downloader adds record keys eligible for subsequent finalization.
Acquisition-only adapters accept the keyword and may ignore it. During `run`,
finalization receives that set; standalone `finalize` receives `None`, meaning all
eligible local records. A staged downloader reaching its budget may still finalize
selected local inputs. Acquisition-only budget stops end the local stages.

Discovery owns resumable scan state and checkpoints. Overrides must respect shared
budgets, preserve admission evidence, checkpoint progress, and use persistence-only
saves for receipts. HTTP hooks and file validators live in `network.py` and the
selected provider; source access rules remain in its guide.

## Native runtimes

An adapter exposing
`execute(settings, command, *, recheck=False, log=print, options=None, checkpoint=None, status_data=None)`
owns stage dispatch instead of using the shared discovery/download orchestration.
`options` is `commands.CommandOptions`; operational values remain in settings.
`checkpoint` coordinates persistence and post-commit publication. `status_data` is
a read-only projected snapshot, without a writable repository baseline.
Litres, Milli Kitaphana, and Common Crawl use this interface. Do not migrate their
stage semantics incidentally while changing shared adapters.
