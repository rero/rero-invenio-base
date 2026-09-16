# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli celery queue commands."""

import sys
from contextlib import contextmanager
from types import SimpleNamespace

from click.testing import CliRunner

from rero_invenio_base.cli.es.queue import queue_pending


def _fake_pool(monkeypatch, message_count=None, error=None):
    """Replace the celery broker pool with one declaring a fixed queue depth."""
    declared = []

    def queue_declare(queue_name, passive=False):
        declared.append((queue_name, passive))
        if error:
            raise error
        return SimpleNamespace(message_count=message_count)

    @contextmanager
    def acquire(block=False):
        yield SimpleNamespace(default_channel=SimpleNamespace(queue_declare=queue_declare))

    queue_cli = sys.modules[queue_pending.callback.__module__]
    monkeypatch.setattr(queue_cli, "celery_app", SimpleNamespace(pool=SimpleNamespace(acquire=acquire)))
    return declared


def test_queue_pending(app, monkeypatch):
    """Pending displays the message count of the named queue."""
    declared = _fake_pool(monkeypatch, message_count=42)
    res = CliRunner().invoke(queue_pending, ["indexer"])
    assert res.exit_code == 0
    assert "indexer: 42 pending task(s)." in res.output
    assert declared == [("indexer", True)]


def test_queue_pending_default_queue(app, monkeypatch):
    """Pending falls back to the celery queue and reports an empty one."""
    declared = _fake_pool(monkeypatch, message_count=0)
    res = CliRunner().invoke(queue_pending, [])
    assert res.exit_code == 0
    assert "celery: 0 pending task(s)." in res.output
    assert declared == [("celery", True)]


def test_queue_pending_unknown_queue(app, monkeypatch):
    """An undeclared queue exits 1 with the broker error."""
    _fake_pool(monkeypatch, error=OSError("NOT_FOUND - no queue 'ghost'"))
    res = CliRunner().invoke(queue_pending, ["ghost"])
    assert res.exit_code == 1
    assert "Error: NOT_FOUND - no queue 'ghost'" in res.output
