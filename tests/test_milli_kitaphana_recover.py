import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "milli_kitaphana"))
import recover


class Response:
    text = '<div class="record" id="catalog-1"><a href="/dl/nbrt_tatarica_Inv_Inv_12101_49">Электронный ресурс</a></div>'

    def __enter__(self): return self
    def __exit__(self, *args): return False


class RecoveryTests(unittest.TestCase):
    def test_explainable_repairs_preserve_original_first(self):
        cases = {
            "nbrt_tatarica_Inv_Inv_12101_49": "nbrt_tatarica_Inv_12101_49",
            "nbrt_tatarica_tatarica_Inv_5905_0": "nbrt_tatarica_Inv_5905_0",
            "nbrt_tatrica_Inv_T_1622660": "nbrt_tatarica_Inv_T_1622660",
            "nbrt_tatarica_Inv_Т_1631453": "nbrt_tatarica_Inv_T_1631453",
            "nbrt/_tatarica_Inv_T_1604513": "nbrt_tatarica_Inv_T_1604513",
        }
        for original, expected in cases.items():
            with self.subTest(original=original):
                self.assertEqual(recover.code_candidates(original), [original, expected])

    def test_url_parsing_ignores_query_and_decodes_typo(self):
        self.assertEqual(recover.code_from_url("http://kitap.tatar.ru/dl/nbrt-tatarica-Inv-%D0%A2-12/?x=1"),
                         "nbrt_tatarica_Inv_Т_12")
        self.assertIsNone(recover.code_from_url("/unrelated/catalog"))

    def test_repaired_code_requires_server_validation_and_all_parts(self):
        original = {"broken": True, "title": "Test"}
        def details(context):
            if "Inv_Inv" in context["meta"]["download_code"]:
                raise ValueError("Unavailable")
            context["meta"]["decryption_key"] = "secret"
        with tempfile.TemporaryDirectory() as temp:
            Path(temp, "source.json").write_text(json.dumps({"parts": [{"url": "part1.pdf", "pagesCount": 5}, {"pagesCount": 50}]}))
            with mock.patch.object(recover, "request", return_value=Response()), \
                 mock.patch.object(recover.downloader, "_scrap_doc_card"), \
                 mock.patch.object(recover.downloader, "_get_details", side_effect=details), \
                 mock.patch.object(recover.downloader, "_get_dh_params"), \
                 mock.patch.object(recover.downloader, "_dh_key_exchange"), \
                 mock.patch.object(recover, "download_part"), \
                 mock.patch.object(recover, "_decrypt_file", return_value=temp):
                result = recover.audit_one("/card", original, {})
        self.assertEqual(result["status"], "limited")
        self.assertTrue(result["link_repaired"])
        self.assertEqual(result["code"], "nbrt_tatarica_Inv_12101_49")
        self.assertEqual(result["available_pages"], 5)
        self.assertNotIn("decryption_key", result["metadata"])
        self.assertEqual(original, {"broken": True, "title": "Test"})

    def test_audit_journal_resumes_without_changing_index(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "report.json")
            path.write_text(json.dumps({"target_count": 2, "records": {"/old": {"status": "limited"}}}))
            with mock.patch.object(recover, "load_index_file", return_value={"/old": {}, "/new": {"broken": True}, "/full": {"downloaded": "full", "decrypted": True}}), \
                 mock.patch.object(recover, "read_config", return_value={}), \
                 mock.patch.object(recover, "audit_one", return_value={"status": "no_download_link"}) as audit, \
                 mock.patch.object(recover, "dump_index") as dump:
                result = recover.recover(path)
            audit.assert_called_once_with("/new", {"broken": True}, {})
            dump.assert_not_called()
            self.assertEqual(result["counts"], {"limited": 1, "no_download_link": 1})

    def test_full_download_with_unfinished_decryption_is_in_scope(self):
        self.assertTrue(recover.unfinished({"downloaded": "full", "decrypted": False}))
        self.assertFalse(recover.unfinished({"downloaded": "full", "decrypted": True}))

    def test_validated_limited_link_fix_preserves_download_state(self):
        index = {"/card": {"download_code": "bad", "broken": True,
                           "downloaded": "limited", "decrypted": True}}
        report = {"records": {"/card": {"status": "limited", "code": "good", "link_repaired": True}}}
        with mock.patch.object(recover, "load_index_file", return_value=index), \
             mock.patch.object(recover, "open_lock"), \
             mock.patch.object(recover, "get_index_file_loc", return_value="/index"), \
             mock.patch.object(recover, "dump_index") as dump:
            recover.apply_link_repairs(report)
        self.assertEqual(index["/card"]["downloaded"], "limited")
        self.assertTrue(index["/card"]["decrypted"])
        self.assertNotIn("broken", index["/card"])
        self.assertEqual(index["/card"]["download_code"], "good")
        dump.assert_called_once_with(index)

    def test_request_sessions_are_closed_and_do_not_leak(self):
        import utils
        session = mock.MagicMock()
        with mock.patch.object(utils.requests, "Session", return_value=session):
            self.assertIsNone(utils._http_session.get())
            with self.assertRaises(ValueError):
                with utils.request_session() as active:
                    self.assertIs(utils._http_session.get(), active)
                    raise ValueError("test")
            self.assertIsNone(utils._http_session.get())
            session.__exit__.assert_called_once()

    def test_download_failure_never_promotes_record_to_full(self):
        original = {"title": "Book", "downloaded": "limited", "decrypted": True}
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp, "report.json")
            path.write_text(json.dumps({"target_count": 1, "records": {
                "/card": {"status": "available_full", "code": "book_1", "metadata": {}, "pages": 10}}}))
            with mock.patch.object(recover, "load_index_file", return_value={"/card": original}), \
                 mock.patch.object(recover, "read_config", return_value={}), \
                 mock.patch.object(recover, "backup_index_snapshot", return_value="backup.zip"), \
                 mock.patch.object(recover, "classify_collections"), \
                 mock.patch.object(recover, "resolve_completed_duplicates"), \
                 mock.patch.object(recover, "apply_link_repairs"), \
                 mock.patch.object(recover.downloader, "_get_details", side_effect=ValueError("unavailable")), \
                 mock.patch.object(recover, "dump_index") as dump:
                result = recover.recover(path, download=True)
            self.assertEqual(result["records"]["/card"]["status"], "download_failed")
            self.assertEqual(original, {"title": "Book", "downloaded": "limited", "decrypted": True})
            dump.assert_not_called()

    def test_obsolete_card_matches_only_one_exact_completed_edition(self):
        identity = {"title": "Book", "author": "Author", "publish_year": "1950", "lang": "Tatar", "collection": "Books"}
        index = {"/old": dict(identity, broken=True),
                 "/new": dict(identity, downloaded="full", decrypted=True, download_code="book_1"),
                 "/different": dict(identity, author="Another Author", broken=True)}
        report = {"records": {"/old": {"status": "no_download_link"}, "/different": {"status": "no_download_link"}}}
        with mock.patch.object(recover, "load_index_file", return_value=index), \
             mock.patch.object(recover, "open_lock"), \
             mock.patch.object(recover, "get_index_file_loc", return_value="/index"), \
             mock.patch.object(recover, "dump_index"):
            recover.resolve_completed_duplicates(report)
        self.assertEqual(report["records"]["/old"]["status"], "duplicate_completed")
        self.assertEqual(index["/old"]["duplicate_of"], "/new")
        self.assertEqual(index["/old"]["downloaded"], "full")
        self.assertNotIn("broken", index["/old"])
        self.assertEqual(report["records"]["/different"]["status"], "no_download_link")

    def test_collections_are_not_failed_document_downloads(self):
        import utils
        meta = {"record_type": "collection"}
        self.assertFalse(recover.unfinished(meta))
        self.assertEqual(utils.get_not_downloaded_docs({"/collection": meta}, False), [])
        index = {"/collection": {}}
        report = {"records": {"/collection": {"status": "no_download_link", "catalog_record_id": "ru\\\\nlrt\\\\collections\\\\101"}}}
        with mock.patch.object(recover, "load_index_file", return_value=index), \
             mock.patch.object(recover, "open_lock"), \
             mock.patch.object(recover, "get_index_file_loc", return_value="/index"), \
             mock.patch.object(recover, "dump_index"):
            recover.classify_collections(report)
        self.assertEqual(report["records"]["/collection"]["status"], "collection")
        self.assertEqual(index["/collection"]["record_type"], "collection")

    def test_validated_code_resolves_obsolete_card_without_title(self):
        index = {"/old": {"broken": True, "download_code": "book_1"},
                 "/new": {"title": "Book", "downloaded": "full", "decrypted": True, "download_code": "book_1"}}
        report = {"records": {"/old": {"status": "available_full", "code": "book_1"}}}
        with mock.patch.object(recover, "load_index_file", return_value=index), \
             mock.patch.object(recover, "open_lock"), \
             mock.patch.object(recover, "get_index_file_loc", return_value="/index"), \
             mock.patch.object(recover, "dump_index"):
            recover.resolve_completed_duplicates(report)
        self.assertEqual(report["records"]["/old"]["status"], "duplicate_completed")
        self.assertEqual(report["records"]["/old"]["match_method"], "download_code")
        self.assertEqual(index["/old"]["title"], "Book")
        self.assertEqual(index["/old"]["duplicate_of"], "/new")

    def test_search_cover_code_must_belong_to_the_exact_card(self):
        response = Response()
        response.text = '''
          <div class="list__item"><a class="list__title-link" href="/tt/ssearch/detail/other/"></a>
            <img class="list__img" src="http://kitap.tatar.ru/obl/nlrt/nbrt_wrong.jpg"></div>
          <div class="list__item"><a class="list__title-link" href="/tt/ssearch/detail/book/"></a>
            <img class="list__img" src="http://kitap.tatar.ru/obl/nlrt/nbrt_tatarica_Inv_T_1510912.jpg"></div>'''
        with mock.patch.object(recover, "request", return_value=response):
            candidates = recover.catalog_cover_candidates("/tt/ssearch/detail/book", {"title": "Book"})
        self.assertEqual(candidates, [("nbrt_tatarica_Inv_T_1510912", "http://kitap.tatar.ru/obl/nlrt/nbrt_tatarica_Inv_T_1510912.jpg")])


if __name__ == "__main__":
    unittest.main()
