# KFU «Азад халык» newspaper

`kfu_azad_halyk` selects <https://repo.kpfu.ru/jspui/handle/net/27528> and keeps
its own manifest under `__artifacts/ingestion/kfu_azad_halyk/`. Add its source entry
from `ingestion.example.yaml` to the operational YAML.

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source kfu_azad_halyk --max-pages 2
.venv/bin/python cli.py --config ingestion.yaml download --source kfu_azad_halyk --limit 1
.venv/bin/python cli.py --config ingestion.yaml run --source kfu_azad_halyk --max-pages 2 --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source kfu_azad_halyk
```

This source reuses KFU's native collection traversal, durable checkpoints,
advertised-count verification, guarded public-file acquisition, atomic storage,
SHA-256/MD5 hashes, and local-file reuse. Publication metadata identifies
`Азад халык` as a newspaper and preserves the original issue title, dates and
series values. Each original file consumes one download item.

The explicit item-language filter is the same as for Il and Shura: recognized
Tatar labels admit files, recognized non-Tatar labels exclude them, and missing
or unknown labels remain held for review. Source language claims are retained
without claiming content verification. Restricted files remain inventoried for
later legitimate access follow-up; they are not requested. Eligible public direct
PDFs are retained unchanged, so there is no resampling or image assembly for
those files. The existing KFU reader fallback applies if public page sets appear
later, with the same 200 DPI colour policy and complete-issue requirement.

Manual CLI verification completed discovery of all 15 records, with the final
advertised count verified and no discovery errors. All 15 had `tt` labels and one
eligible public PDF each. A bounded `run --max-pages 2 --limit 1` downloaded
`net/27569` (`№ 15, 1906`) as an unchanged eight-page PDF of 8,466,638 bytes,
recording SHA-256 `24b2ab8292b4ff31150d1d93ee28e9033870f4e5eedc1b02188967c503256bfd`
and MD5 `ff0560df9b939d12abf599a638f998ec`. Fourteen files remain pending.
An isolated repeat using the completed record reused its verified local original
with zero HTTP requests. Compilation and diff checks passed; no automated tests
were added.
