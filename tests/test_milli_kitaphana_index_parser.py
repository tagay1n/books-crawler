import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import index as mk_index  # noqa: E402


class _FakeProgress:
    def __init__(self, *args, **kwargs):
        self.updates = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, *args, **kwargs):
        return 1

    def update(self, task, **kwargs):
        self.updates.append((task, kwargs))


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None


def _find_page(params):
    for key, value in params:
        if key == "page":
            return int(value)
    raise AssertionError("Missing page parameter")


class MilliIndexParserTests(unittest.TestCase):
    def test_create_newest_index_paginates_and_parses_meta(self):
        page_1 = """
<html><body>
  <div class="search-nav__item search-nav__item_sm-ta-c">
    <span class="search-nav__text">Найдено: 2</span>
  </div>
  <div class="list__col-text">
    <h3 class="list__title">
      <a class="list__title-link" href="/tt/ssearch/detail/a/">NEW!!! Title A</a>
    </h3>
    <dl class="list__dl">
      <dt>Бастырып чыгару елы:</dt><dd>[2001]</dd>
      <dt>Тел:</dt><dd>tatar</dd>
      <dt>Коллекция:</dt><dd>Main</dd>
    </dl>
    <ul class="tag list__tag">
      <li class="tag__item"><a>tag1</a></li>
      <li class="tag__item"><a>tag2</a></li>
    </ul>
    <p class="list__description">  Some   Author  </p>
  </div>
  <ul class="pagination">
    <li class="active">1</li>
    <li>2</li>
  </ul>
</body></html>
"""
        page_2 = """
<html><body>
  <div class="search-nav__item search-nav__item_sm-ta-c">
    <span class="search-nav__text">Найдено: 2</span>
  </div>
  <div class="list__col-text">
    <h3 class="list__title">
      <a class="list__title-link" href="/tt/ssearch/detail/b/">Title B</a>
    </h3>
    <dl class="list__dl">
      <dt>Год публикации:</dt><dd>2002</dd>
      <dt>Язык:</dt><dd>Russian label language</dd>
      <dt>Коллекция:</dt><dd>Russian label collection</dd>
    </dl>
  </div>
  <ul class="pagination">
    <li>1</li>
    <li class="active">2</li>
  </ul>
</body></html>
"""
        html_by_page = {1: page_1, 2: page_2}

        def _fake_get(url, params, headers, verify):
            self.assertEqual(url, mk_index.ENTRY_POINT)
            self.assertFalse(verify)
            page = _find_page(params)
            return _FakeResponse(html_by_page[page])

        with mock.patch.object(mk_index, "Progress", _FakeProgress):
            with mock.patch.object(mk_index.requests, "get", side_effect=_fake_get):
                parsed = mk_index._create_newest_index("tat")

        self.assertEqual(set(parsed.keys()), {"/tt/ssearch/detail/a", "/tt/ssearch/detail/b"})
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["title"], "Title A")
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["publish_year"], "[2001]")
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["lang"], "tatar")
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["collection"], "Main")
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["tags"], ["tag1", "tag2"])
        self.assertEqual(parsed["/tt/ssearch/detail/a"]["author"], "Some Author")
        self.assertEqual(parsed["/tt/ssearch/detail/b"]["publish_year"], "2002")
        self.assertEqual(parsed["/tt/ssearch/detail/b"]["lang"], "Russian label language")
        self.assertEqual(parsed["/tt/ssearch/detail/b"]["collection"], "Russian label collection")

    def test_index_aggregates_languages_collections_and_dumps_merged_result(self):
        tat_index = {"/tat": {"title": "Tat"}}
        ara_index = {"/ara": {"title": "Ara"}}
        collection_index = {"/collection": {"title": "Collection"}}
        old_index = {"/old": {"title": "Old"}}
        merged_index = {"/merged": {"title": "Merged"}}

        with mock.patch.object(mk_index, "backup_index_snapshot", return_value="/tmp/backup.zip"):
            with mock.patch.object(mk_index, "_create_newest_index", side_effect=[tat_index, ara_index]) as m_create:
                with mock.patch.object(mk_index, "_create_collection_index", return_value=collection_index) as m_collection:
                    with mock.patch.object(mk_index, "load_index_file", return_value=old_index):
                        with mock.patch.object(mk_index, "_merge_indexes", return_value=merged_index) as m_merge:
                            with mock.patch.object(mk_index, "dump_index") as m_dump:
                                mk_index.index()

        self.assertEqual(m_create.call_count, 2)
        self.assertEqual(m_create.call_args_list[0].args[0], "tat")
        self.assertEqual(m_create.call_args_list[1].args[0], "ara")
        m_collection.assert_called_once_with(mk_index.COLLECTION_QUERIES[0])
        m_merge.assert_called_once_with(
            {"/tat": {"title": "Tat"}, "/ara": {"title": "Ara"}, "/collection": {"title": "Collection"}},
            old_index,
        )
        m_dump.assert_called_once_with(merged_index)

    def test_create_collection_index_uses_collection_filter_params(self):
        page = """
<html><body>
  <div class="search-nav__item search-nav__item_sm-ta-c">
    <span class="search-nav__text">Найдено: 1</span>
  </div>
  <div class="list__col-text">
    <h3 class="list__title">
      <a class="list__title-link" href="/ru/ssearch/detail/c/">Title C</a>
    </h3>
    <dl class="list__dl">
      <dt>Язык:</dt><dd>Башкирский</dd>
    </dl>
  </div>
  <ul class="pagination">
    <li class="active">1</li>
  </ul>
</body></html>
"""

        def _fake_get(url, params, headers, verify):
            self.assertEqual(url, mk_index.ENTRY_POINT)
            self.assertIn(("fattr", "fond_sf"), params)
            self.assertIn(("fq", "COLLECTION_12"), params)
            self.assertIn(("sort", "record-create-date"), params)
            self.assertIn(("page", 1), params)
            self.assertNotIn(("attr", "code-language_t"), params)
            return _FakeResponse(page)

        with mock.patch.object(mk_index, "Progress", _FakeProgress):
            with mock.patch.object(mk_index.requests, "get", side_effect=_fake_get):
                parsed = mk_index._create_collection_index(mk_index.COLLECTION_QUERIES[0])

        self.assertEqual(set(parsed.keys()), {"/ru/ssearch/detail/c"})
        self.assertEqual(parsed["/ru/ssearch/detail/c"]["lang"], "Башкирский")


if __name__ == "__main__":
    unittest.main()
