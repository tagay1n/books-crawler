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
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def add_task(self, *args, **kwargs):
        return 1

    def update(self, *args, **kwargs):
        return None


class _FakeResponse:
    def __init__(self, text):
        self.text = text

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def raise_for_status(self):
        return None


class MilliIndexEdgeTests(unittest.TestCase):
    def test_create_newest_index_raises_when_pagination_missing(self):
        html = """
<html><body>
  <div class="search-nav__item search-nav__item_sm-ta-c">
    <span class="search-nav__text">Найдено: 1</span>
  </div>
  <div class="list__col-text">
    <h3 class="list__title"><a class="list__title-link" href="/tt/ssearch/detail/a/">A</a></h3>
    <dl class="list__dl"><dt>Тел:</dt><dd>tat</dd></dl>
  </div>
</body></html>
"""
        with mock.patch.object(mk_index, "Progress", _FakeProgress):
            with mock.patch.object(mk_index.requests, "get", return_value=_FakeResponse(html)):
                with self.assertRaises(AttributeError):
                    mk_index._create_newest_index("tat")

    def test_create_newest_index_raises_when_total_count_mismatch(self):
        html = """
<html><body>
  <div class="search-nav__item search-nav__item_sm-ta-c">
    <span class="search-nav__text">Найдено: 2</span>
  </div>
  <div class="list__col-text">
    <h3 class="list__title"><a class="list__title-link" href="/tt/ssearch/detail/a/">A</a></h3>
    <dl class="list__dl"><dt>Тел:</dt><dd>tat</dd></dl>
  </div>
  <ul class="pagination">
    <li class="active">1</li>
  </ul>
</body></html>
"""
        with mock.patch.object(mk_index, "Progress", _FakeProgress):
            with mock.patch.object(mk_index.requests, "get", return_value=_FakeResponse(html)):
                with self.assertRaises(AssertionError) as ctx:
                    mk_index._create_newest_index("tat")

        self.assertIn("Expected 2 documents, but indexed 1 documents.", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
