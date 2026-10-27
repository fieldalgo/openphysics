# Copyright 2026 Yongha Kim (FieldAlgo)
# SPDX-License-Identifier: Apache-2.0
"""One-way chains of named stages with stage-labelled failures."""
from contextlib import contextmanager


class OneWayChain:
    """Run named stages in order; a failing stage raises ``error(stage, exc, **context)``.

    ``error`` builds the exception to raise; it is raised ``from`` the original,
    so the cause is retained. Each stage that finishes is appended to
    ``completed``. There is no iteration or feedback between stages.
    """

    def __init__(self, error):
        if not callable(error):
            raise ValueError("error must build an exception from (stage, exc, **context)")
        self._error = error
        self._completed = []

    @property
    def completed(self):
        """Names of the stages that finished, in order."""
        return tuple(self._completed)

    @contextmanager
    def stage(self, name, **context):
        """Run the body as stage ``name``; ``context`` is passed to ``error`` on failure."""
        try:
            yield
        except Exception as exc:
            raise self._error(name, exc, **context) from exc
        self._completed.append(name)
