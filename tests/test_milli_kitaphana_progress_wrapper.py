import sys
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
MILLI_DIR = ROOT / "milli_kitaphana"
if str(MILLI_DIR) not in sys.path:
    sys.path.insert(0, str(MILLI_DIR))

import progress_wrapper as mk_progress  # noqa: E402


class _FakeLive:
    def __init__(self, *_args, **_kwargs):
        self.entered = False
        self.stopped = False
        self.exited = False

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, exc_type, exc, tb):
        self.exited = True
        return False

    def stop(self):
        self.stopped = True


class MilliProgressWrapperTests(unittest.TestCase):
    def test_wrapper_context_manager_and_main_aux_tasks(self):
        context = {"meta": {"download_code": "dc1"}}
        with mock.patch.object(mk_progress, "Live", _FakeLive):
            wrapper = mk_progress.ProgressWrapper(context, "/card/a")
            before = len(wrapper._main[0].columns)
            with wrapper as pw:
                pw.main("Working")
                d_task = pw.download("part1.zip")
                pw._aux.stop_task(d_task)
                x_task = pw.decrypt("part1.zip", total_size=100)
                pw._aux.stop_task(x_task)

            self.assertTrue(wrapper.live.entered)
            self.assertTrue(wrapper.live.stopped)
            self.assertTrue(wrapper.live.exited)
            self.assertEqual(len(wrapper._main[0].columns), before - 1)
            self.assertIs(context["progress"], wrapper)

    def test_pop_if_many_tasks_removes_old_completed_tasks(self):
        context = {"meta": {"download_code": "dc2"}}
        with mock.patch.object(mk_progress, "Live", _FakeLive):
            wrapper = mk_progress.ProgressWrapper(context, "/card/b")
            for i in range(10):
                task = wrapper._aux.add_task(f"done-{i}", start=True)
                wrapper._aux.stop_task(task)

            wrapper._pop_if_many_tasks(queue_size=4)
            self.assertLessEqual(len(wrapper._aux._tasks), 4)


if __name__ == "__main__":
    unittest.main()
