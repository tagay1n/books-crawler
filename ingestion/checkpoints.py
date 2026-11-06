"""Explicit progress commit followed by optional post-commit work."""


class Checkpoint:
    def __init__(self, after_commit=None):
        self.after_commit = after_commit

    def __call__(self, repository, data):
        repository.save(data)
        if self.after_commit is not None:
            self.after_commit(repository, data)
