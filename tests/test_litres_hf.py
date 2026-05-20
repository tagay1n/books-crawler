import importlib.util
import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
LITRES_DIR = ROOT / "litres"
LITRES_HF = ROOT / "litres" / "hf.py"
if str(LITRES_DIR) not in sys.path:
    sys.path.insert(0, str(LITRES_DIR))
spec = importlib.util.spec_from_file_location("litres_hf_for_tests", LITRES_HF)
litres_hf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(litres_hf)


class _FakeHfApi:
    calls = []

    def upload_folder(self, **kwargs):
        self.calls.append(kwargs)


class LitresHfTests(unittest.TestCase):
    def test_upload_to_hf_uses_repo_root_artifacts_markdown_dir(self):
        _FakeHfApi.calls = []

        with (
            mock.patch.dict(sys.modules, {"huggingface_hub": mock.Mock(HfApi=_FakeHfApi)}),
            mock.patch.object(litres_hf, "get_in_workdir", side_effect=lambda path: f"/repo/litres/{path}"),
        ):
            litres_hf.upload_to_hf()

        self.assertEqual(
            _FakeHfApi.calls,
            [
                {
                    "folder_path": "/repo/litres/../__artifacts/litres/markdown",
                    "repo_id": "yasalma/tt-litres-books",
                    "repo_type": "dataset",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
