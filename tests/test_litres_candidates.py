import csv
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_CANDIDATES = ROOT / "litres" / "candidates.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_candidates_for_tests", LITRES_CANDIDATES)
litres_candidates = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_candidates)


class LitresCandidatesTests(unittest.TestCase):
    def test_export_review_writes_sorted_tsv(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = _artifacts(tmp)
            _write_json(
                artifacts / "candidates-index.json",
                {
                    "low": {
                        "status": "candidate",
                        "score": 40,
                        "content_type": "text",
                        "title": "Low",
                        "url": "https://www.litres.ru/book/a/low/",
                    },
                    "high": {
                        "status": "candidate",
                        "score": 150,
                        "content_type": "pdf",
                        "litres_language": "ru",
                        "title": "High",
                        "author": "Author",
                        "signals": ["tatar_letters", "known_author"],
                        "url": "https://www.litres.ru/book/a/high/",
                    },
                },
            )

            with mock.patch.object(litres_candidates, "get_in_workdir", side_effect=_get_in_tmp(tmp)):
                litres_candidates.export_review()

            rows = _read_tsv(artifacts / "candidates-review.tsv")
            self.assertEqual(["high", "low"], [row["id"] for row in rows])
            self.assertEqual("150", rows[0]["score"])
            self.assertEqual("tatar_letters,known_author", rows[0]["signals"])
            self.assertEqual("https://www.litres.ru/book/a/high/", rows[0]["url"])

    def test_sync_review_updates_statuses(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = _artifacts(tmp)
            _write_json(
                artifacts / "candidates-index.json",
                {
                    "a": {"status": "candidate", "title": "A"},
                    "b": {"status": "rejected", "title": "B"},
                },
            )
            _write_tsv(
                artifacts / "candidates-review.tsv",
                [
                    {"id": "a", "status": "accepted"},
                    {"id": "b", "status": "maybe"},
                    {"id": "unknown", "status": "accepted"},
                ],
            )

            with mock.patch.object(litres_candidates, "get_in_workdir", side_effect=_get_in_tmp(tmp)):
                litres_candidates.sync_review()

            candidates = _read_json(artifacts / "candidates-index.json")
            self.assertEqual("accepted", candidates["a"]["status"])
            self.assertEqual("maybe", candidates["b"]["status"])

    def test_sync_review_rejects_invalid_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = _artifacts(tmp)
            _write_json(artifacts / "candidates-index.json", {"a": {"status": "candidate"}})
            _write_tsv(artifacts / "candidates-review.tsv", [{"id": "a", "status": "yes"}])

            with mock.patch.object(litres_candidates, "get_in_workdir", side_effect=_get_in_tmp(tmp)):
                with self.assertRaisesRegex(ValueError, "Invalid review status"):
                    litres_candidates.sync_review()

    def test_import_accepted_adds_new_books_and_skips_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            artifacts = _artifacts(tmp)
            existing_url = "https://www.litres.ru/book/a/existing/"
            new_url = "https://www.litres.ru/book/a/new/"
            _write_json(
                artifacts / "books-index.json",
                {"existing": {"title": "Existing", "url": existing_url, "content_type": "text"}},
            )
            _write_json(
                artifacts / "candidates-index.json",
                {
                    "accepted-new": {
                        "status": "accepted",
                        "title": "New",
                        "author": "Author",
                        "full_name": "New - Author",
                        "summary": "Summary",
                        "url": new_url,
                        "content_type": "pdf",
                        "subscription": True,
                        "litres_language": "ru",
                    },
                    "accepted-existing": {
                        "status": "accepted",
                        "title": "Existing",
                        "url": existing_url,
                        "content_type": "text",
                    },
                    "rejected": {
                        "status": "rejected",
                        "title": "Rejected",
                        "url": "https://www.litres.ru/book/a/rejected/",
                        "content_type": "text",
                    },
                },
            )

            with mock.patch.object(litres_candidates, "get_in_workdir", side_effect=_get_in_tmp(tmp)):
                litres_candidates.import_accepted()

            books = _read_json(artifacts / "books-index.json")
            imported = books[litres_candidates.get_hash(new_url)]
            self.assertEqual(2, len(books))
            self.assertEqual("New", imported["title"])
            self.assertEqual("pdf", imported["content_type"])
            self.assertEqual(False, imported["downloaded"])
            self.assertEqual("ru", imported["litres_language"])


def _artifacts(tmp):
    artifacts = Path(tmp) / "__artifacts" / "litres"
    artifacts.mkdir(parents=True)
    return artifacts


def _get_in_tmp(tmp):
    def _get_in_workdir(path):
        return str(Path(tmp) / path.removeprefix("../"))

    return _get_in_workdir


def _write_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write_tsv(path, rows):
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=("id", "status"), delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _read_tsv(path):
    with path.open("r", encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f, delimiter="\t"))


if __name__ == "__main__":
    unittest.main()
