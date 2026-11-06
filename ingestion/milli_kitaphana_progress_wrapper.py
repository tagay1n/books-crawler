"""Rich progress UI wrapper combining main status and per-part download/decrypt tasks."""

from rich.progress import Progress, TextColumn, ProgressColumn, TaskProgressColumn, Text, SpinnerColumn, TimeElapsedColumn, FileSizeColumn, TransferSpeedColumn
from rich.live import Live
from rich.console import Group
from rich.panel import Panel

class ProgressWrapper():
    def __init__(self, context, card_path):
        main_progress = Progress(
            TimeElapsedColumn(),
            TextColumn(
                f"[bold cyan]'{context['meta']['download_code']}({card_path})':"),
            TextColumn("[progress.description]{task.description}"),
            SpinnerColumn(spinner_name="dots", style="bold cyan"),
        )
        main_task = main_progress.add_task("Preparing", start=True)
        self._main = (main_progress, main_task)

        aux_progress = Progress(
            CheckBoxColumn(),
            TextColumn("[progress.description]{task.description}"),
            FileSizeColumn(),
            TransferSpeedColumn(),
            TaskProgressColumn(),
        )
        self._aux = aux_progress

        progress_group = Group(
            aux_progress,
            Panel(main_progress),
        )

        self.live = Live(progress_group)
        context["progress"] = self

    def __enter__(self):
        self.live.__enter__()
        return self

    def __exit__(self, type, value, traceback):
        # remove spinner column
        self._main[0].columns = self._main[0].columns[:-1]
        self.live.stop()
        self.live.__exit__(type, value, traceback)

    def main(self, description):
        progress, task = self._main
        progress.update(task, description=description)

    def download(self, part_name):
        self._pop_if_many_tasks()
        task = self._aux.add_task(
            f"Downloading {part_name}",
            start=True,
        )
        self._aux._tasks[task]._reset()
        return task

    def decrypt(self, part_name, total_size=None):
        self._pop_if_many_tasks()
        return self._aux.add_task(
            f"Decrypting {part_name}",
            start=True,
            total=total_size
        )

    def _pop_if_many_tasks(self, queue_size=16):
        current_tasks = self._aux._tasks
        if len(current_tasks) <= queue_size:
            return

        completed_tasks = [t for t in current_tasks.values() if t.stop_time]
        incomplete_tasks_count = len(current_tasks) - len(completed_tasks)
        if incomplete_tasks_count >= queue_size:
            to_remove = completed_tasks
        else:
            # sort completed tasks and remain queue_size - incomplete_tasks_count
            to_remove = sorted(completed_tasks, key=lambda i: i.start_time, reverse=True)[
                queue_size - incomplete_tasks_count:]

        for ct in to_remove:
            try:
                del self._aux._tasks[ct.id]
            except Exception:
                pass


class CheckBoxColumn(ProgressColumn):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.complete = False

    def render(self, task: "Task") -> Text:
        if task.stop_time:
            return Text("[x]", style="green")
        else:
            return Text("[ ]", style="yellow")

    def update(self, complete):
        self.complete = complete
