# Magarif archive attachments

The `magarif` adapter follows the public educational archive at
<https://magarif-uku.ru/documents> and its native pagination. It retains record
headings, dates, descriptions and explicitly linked attachments. Supported
same-origin documents are acquired; unsupported formats and external file
references remain visible in the manifest. Admission is by archive membership;
content language and completeness are unverified. This is separate from the
[Magarif-Vakyt textbook publisher](magarif-vakyt.md).

```yaml
sources:
  magarif:
    archive_url: https://magarif-uku.ru/documents
```

```bash
.venv/bin/python cli.py --config ingestion.yaml discover --source magarif
.venv/bin/python cli.py --config ingestion.yaml download --source magarif --limit 1
.venv/bin/python cli.py --config ingestion.yaml status --source magarif
```

See [shared configuration, budgets and recovery](operations.md).
