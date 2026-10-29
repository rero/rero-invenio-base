# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli celery queue commands."""

import re
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from click.testing import CliRunner

from rero_invenio_base.cli.queue import queue_list, queue_pending, queue_purge, queue_stats


def _fake_celery(monkeypatch, depths=None, replies=None):
    """Replace the celery app with a fake broker and fake worker replies.

    :param depths: message count by queue name; any other queue is unknown to the broker.
    :param replies: worker inspect replies by method name (stats, active, reserved, scheduled).
    :returns: the list of queues declared on the broker, as (name, passive) tuples.
    """
    depths = depths or {}
    replies = replies or {}
    declared = []

    def _known(queue_name):
        if queue_name not in depths:
            raise OSError(f"NOT_FOUND - no queue '{queue_name}'")
        return depths[queue_name]

    def queue_declare(queue_name, passive=False):
        declared.append((queue_name, passive))
        return SimpleNamespace(message_count=_known(queue_name))

    @contextmanager
    def connection(block=False):
        yield SimpleNamespace(default_channel=SimpleNamespace(queue_declare=queue_declare, queue_purge=_known))

    inspect = SimpleNamespace(
        **{name: (lambda name=name: replies.get(name)) for name in ("stats", "active", "reserved", "scheduled")}
    )
    queue_cli = sys.modules[queue_pending.callback.__module__]
    monkeypatch.setattr(
        queue_cli,
        "celery_app",
        SimpleNamespace(
            pool=SimpleNamespace(acquire=connection),
            connection=connection,
            control=SimpleNamespace(inspect=lambda timeout: inspect),
            conf=SimpleNamespace(task_default_queue="celery", task_queues=[SimpleNamespace(name="indexer")]),
        ),
    )
    return declared


def test_queue_pending(app, monkeypatch):
    """Pending displays the message count of the named queue."""
    declared = _fake_celery(monkeypatch, depths={"indexer": 42})
    res = CliRunner().invoke(queue_pending, ["indexer"])
    assert res.exit_code == 0
    assert "indexer: 42 pending task(s)." in res.output
    assert declared == [("indexer", True)]


def test_queue_pending_default_queue(app, monkeypatch):
    """Pending falls back to the celery queue and reports an empty one."""
    declared = _fake_celery(monkeypatch, depths={"celery": 0})
    res = CliRunner().invoke(queue_pending, [])
    assert res.exit_code == 0
    assert "celery: 0 pending task(s)." in res.output
    assert declared == [("celery", True)]


def test_queue_pending_unknown_queue(app, monkeypatch):
    """An undeclared queue exits 1 with the broker error."""
    _fake_celery(monkeypatch)
    res = CliRunner().invoke(queue_pending, ["ghost"])
    assert res.exit_code == 1
    assert "Error: NOT_FOUND - no queue 'ghost'" in res.output


@pytest.mark.parametrize("command", [queue_list, queue_stats])
def test_queue_without_workers(app, monkeypatch, command):
    """List and stats report when no worker answers the inspection."""
    _fake_celery(monkeypatch)
    res = CliRunner().invoke(command, ["--timeout", "0.5"])
    assert res.exit_code == 0
    assert "No workers responded within 0.5s." in res.output


def test_queue_list(app, monkeypatch):
    """List counts the tasks of each worker and the depth of each queue."""
    _fake_celery(
        monkeypatch,
        depths={"celery": 3},
        replies={
            "stats": {"w1": {}, "w2": {}},
            "active": {"w1": ["t1", "t2"]},
            "scheduled": {"w2": ["t3"]},
        },
    )
    res = CliRunner().invoke(queue_list, [])
    assert res.exit_code == 0
    assert re.search(r"w1\s+2\s+0\s+0\n", res.output)
    assert re.search(r"w2\s+0\s+0\s+1\n", res.output)
    assert re.search(r"celery\s+3\n", res.output)
    assert re.search(r"indexer\s+\?\n", res.output)


def test_queue_stats(app, monkeypatch):
    """Stats prints the worker statistics as JSON."""
    _fake_celery(monkeypatch, replies={"stats": {"w1": {"pid": 1234}}})
    res = CliRunner().invoke(queue_stats, [])
    assert res.exit_code == 0
    assert '"pid": 1234' in res.output


def test_queue_purge(app, monkeypatch):
    """Purge reports how many tasks it removed from the queue."""
    _fake_celery(monkeypatch, depths={"indexer": 4})
    res = CliRunner().invoke(queue_purge, ["indexer", "--yes-i-know"])
    assert res.exit_code == 0
    assert "Purged 4 task(s) from 'indexer'." in res.output


def test_queue_purge_unknown_queue(app, monkeypatch):
    """Purging an undeclared queue exits 1 with the broker error."""
    _fake_celery(monkeypatch)
    res = CliRunner().invoke(queue_purge, ["ghost", "--yes-i-know"])
    assert res.exit_code == 1
    assert "Error: NOT_FOUND - no queue 'ghost'" in res.output
