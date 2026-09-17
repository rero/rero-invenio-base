# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli elasticsearch commands."""

import re
import sys
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from elasticsearch import NotFoundError, RequestError
from invenio_search import current_search, current_search_client

from rero_invenio_base.cli.es.alias import delete_alias, get_alias, put_alias
from rero_invenio_base.cli.es.index import (
    _watch_reindex_task,
    close_index,
    create_index,
    open_index,
    rebuild_index,
    switch_index,
    update_mapping,
)
from rero_invenio_base.cli.es.snapshot.cli import (
    WAIT_REQUEST_TIMEOUT,
    create_snapshot,
    delete_snapshot,
    list_snapshot,
    restore_snapshot,
)
from rero_invenio_base.cli.es.snapshot.repository import (
    create_repository,
    delete_repository,
    list_repository,
)
from rero_invenio_base.cli.es.task import task_watch


def test_cli_es_index_alias(script_info, app, es_runner, new_index_name1, new_index_name2):
    """Test index and aliases command line interface."""
    runner = es_runner

    res = runner.invoke(create_index, ["records", new_index_name1], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(put_alias, [new_index_name1, "records"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(get_alias, [], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(update_mapping, ["-a", "records"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(close_index, [], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(open_index, [], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(create_index, ["records", new_index_name2], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(switch_index, [new_index_name1, new_index_name2], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(get_alias, [], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(delete_alias, [new_index_name2, "records", "--yes-i-know"], obj=script_info)
    assert res.exit_code == 0


def test_task_watch_finished_task(script_info, app, es_runner, monkeypatch):
    """A task gone from the task list has completed, it is not an error."""

    def tasks_get(task):
        raise NotFoundError(404, "resource_not_found_exception", {})

    task_cli = sys.modules[task_watch.callback.__module__]
    monkeypatch.setattr(task_cli, "current_search_client", SimpleNamespace(tasks=SimpleNamespace(get=tasks_get)))
    res = es_runner.invoke(task_watch, ["node:1"], obj=script_info)
    assert res.exit_code == 0
    assert "Finished task: node:1" in res.output


def test_cli_es_alias_error_exits(script_info, app, es_runner):
    """A failing alias operation exits non-zero instead of reporting success."""
    res = es_runner.invoke(put_alias, ["nosuchindex", "records"], obj=script_info)
    assert res.exit_code == 1


def test_cli_es_create_index_error(script_info, app, es_runner, new_index_name1):
    """Creating an index twice reports the error instead of raising."""
    res = es_runner.invoke(create_index, ["records", new_index_name1], obj=script_info)
    assert res.exit_code == 0
    assert f"Index {new_index_name1} created." in res.output

    res = es_runner.invoke(create_index, ["records", new_index_name1], obj=script_info)
    assert res.exit_code == 1
    assert "ERROR CREATE" in res.output


def test_cli_es_snapshot_repository(script_info, app, es_runner, new_index_name1):
    """Test snapshot repository command line interface."""
    runner = es_runner

    res = runner.invoke(create_repository, ["tests", "snap"], obj=script_info)
    if res.exit_code != 0:
        pytest.skip("cluster started without path.repo: snapshot repositories cannot be registered")

    res = runner.invoke(list_repository, [], obj=script_info)

    assert res.exit_code == 0

    res = runner.invoke(delete_repository, ["tests", "--yes-i-know"], obj=script_info)
    assert res.exit_code == 0


def _old_index():
    """Return a fixed past-dated index name for rebuild tests."""
    return "records-record-v1.0.0-20250101"


def _new_index():
    """Return the index name rebuild would create today."""
    registered = next(iter(current_search.aliases.get("records")))
    return f"{registered}-{datetime.now(UTC).strftime('%Y%m%d')}"


def test_rebuild_index_unknown_resource(rebuild_runner, script_info):
    """Rebuild exits 1 for an unknown alias."""
    res = rebuild_runner.invoke(rebuild_index, ["nonexistent"], obj=script_info)
    assert res.exit_code == 1
    assert "Unknown resource" in res.output


def test_rebuild_index_fresh(rebuild_runner, script_info):
    """Rebuild creates a fresh index and registers the alias when none exist."""
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=script_info)
    assert res.exit_code == 0
    assert current_search_client.indices.exists_alias(name="records")


def test_rebuild_index_fresh_new_index_already_exists(rebuild_runner, script_info):
    """Rebuild exits 1 when the target index exists but the alias is missing."""
    current_search_client.indices.create(index=_new_index(), body={})
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=script_info)
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_rebuild_index_noop(rebuild_runner, script_info):
    """Rebuild is a no-op when the alias already points to today's index."""
    today_index = _new_index()
    current_search_client.indices.create(index=today_index, body={})
    current_search_client.indices.put_alias(index=today_index, name="records")
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=script_info)
    assert res.exit_code == 0
    assert "Nothing to do" in res.output


def test_rebuild_index_new_already_exists(rebuild_runner, script_info):
    """Rebuild exits 1 when the new index already exists and the alias points elsewhere."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    current_search_client.indices.create(index=_new_index(), body={})
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=script_info)
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_rebuild_index_normal_confirm(rebuild_runner, script_info):
    """Rebuild switches alias and deletes old index when confirmed."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates"],
        input="y\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    assert not current_search_client.indices.exists(index=old)
    assert current_search_client.indices.exists(index=_new_index())
    assert current_search_client.indices.exists_alias(name="records")


def test_rebuild_index_keeps_the_source_when_not_waiting(rebuild_runner, script_info):
    """--interval 0 does not wait, so it must not switch nor delete anything."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--interval", "0"],
        obj=script_info,
    )
    assert res.exit_code == 0
    assert "Not waiting for the task" in res.output
    assert current_search_client.indices.exists(index=old)
    assert list(current_search_client.indices.get_alias(name="records")) == [old]


def test_rebuild_index_normal_abort(rebuild_runner, script_info):
    """Rebuild leaves cluster unchanged when the user declines the confirmation."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates"],
        input="n\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    assert current_search_client.indices.exists(index=old)
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == [old]


def test_rebuild_index_inplace(rebuild_runner, script_info):
    """--inplace rebuilds under the same name: alias returns to old, temp deleted."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--inplace"],
        input="y\ny\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    assert current_search_client.indices.exists(index=old)
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == [old]
    temp_indices = list(current_search_client.indices.get(f"{old}-tmp-*").keys())
    assert not temp_indices


def test_rebuild_index_inplace_abort_second_confirm(rebuild_runner, script_info):
    """--inplace abort at final confirm: alias stays on temp, old index recreated but not live."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--inplace"],
        input="y\nn\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    temp_indices = list(current_search_client.indices.get(f"{old}-tmp-*").keys())
    assert len(temp_indices) == 1
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == temp_indices
    assert current_search_client.indices.exists(index=old)


class _FakeTasks:
    """Tasks API returning canned responses and recording the calls."""

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def get(self, task, **kwargs):
        """Record the call and return (or raise) the next canned response."""
        self.calls.append((task, kwargs))
        res = self.responses.pop(0)
        if isinstance(res, Exception):
            raise res
        return res


def _fake_watch(monkeypatch, responses):
    """Install a fake tasks API and a fake sleep, return both recorders."""
    index_cli = sys.modules[_watch_reindex_task.__module__]
    tasks = _FakeTasks(responses)
    sleeps = []
    monkeypatch.setattr(index_cli, "current_search_client", SimpleNamespace(tasks=tasks))
    monkeypatch.setattr(index_cli.time, "sleep", sleeps.append)
    return tasks, sleeps


def test_watch_reindex_task_polls_without_server_timeout(monkeypatch, capsys):
    """The interval paces the client loop, it is never sent to Search."""
    tasks, sleeps = _fake_watch(
        monkeypatch,
        [
            {"completed": False, "task": {"status": {"created": 10, "total": 30}}},
            {"completed": False, "task": {"status": {"created": 20, "total": 30}}},
            {"completed": True, "response": {}},
        ],
    )

    assert _watch_reindex_task("task-1", 5, verbose=True)
    assert [kwargs for _, kwargs in tasks.calls] == [{}, {}, {}]
    assert sleeps == [5, 5]
    output = capsys.readouterr().out
    assert "task-1 0 seconds ... 10/30" in output
    assert "task-1 5 seconds ... 20/30" in output
    assert "Finished task: task-1 10 seconds." in output


def test_watch_reindex_task_failures(monkeypatch):
    """A task reporting failures makes the watch return False."""
    _fake_watch(monkeypatch, [{"completed": True, "response": {"failures": ["boom"]}}])
    assert not _watch_reindex_task("task-2", 5, verbose=False)


def test_watch_reindex_task_vanished(monkeypatch):
    """A task that is gone or whose index got closed counts as finished."""
    _fake_watch(monkeypatch, [NotFoundError(404, "resource_not_found_exception", {})])
    assert _watch_reindex_task("task-3", 5, verbose=False)

    _fake_watch(monkeypatch, [RequestError(400, "index_closed_exception", {})])
    assert _watch_reindex_task("task-4", 5, verbose=False)


def test_watch_reindex_task_propagates_other_errors(monkeypatch):
    """Any other request error is not swallowed."""
    _fake_watch(monkeypatch, [RequestError(400, "illegal_argument_exception", {})])
    with pytest.raises(RequestError):
        _watch_reindex_task("task-5", 5, verbose=False)


def _fake_snapshot_client(monkeypatch, captured, error=None, restore_error=None):
    """Keep the real cat API but capture the snapshot and indices calls."""

    def snapshot_create(repository, name, body=None, **kwargs):
        captured["create"] = {"repository": repository, "name": name, "body": body, **kwargs}
        if error:
            raise error
        return {"accepted": True}

    def snapshot_restore(repository, name, body=None, **kwargs):
        captured["restore"] = {"repository": repository, "name": name, "body": body}
        if restore_error:
            raise restore_error
        return {"accepted": True}

    def indices_delete(index=None, **kwargs):
        captured["delete"] = index
        return {"acknowledged": True}

    def indices_close(index=None, **kwargs):
        captured["close"] = index
        return {"acknowledged": True}

    def indices_open(index=None, **kwargs):
        captured["open"] = index
        return {"acknowledged": True}

    snapshot_cli = sys.modules[create_snapshot.callback.__module__]
    monkeypatch.setattr(
        snapshot_cli,
        "current_search_client",
        SimpleNamespace(
            cat=current_search_client.cat,
            snapshot=SimpleNamespace(create=snapshot_create, restore=snapshot_restore),
            indices=SimpleNamespace(delete=indices_delete, close=indices_close, open=indices_open),
        ),
    )


def test_snapshot_create_no_match(script_info, app, es_runner):
    """Create refuses to snapshot a pattern that matches no index."""
    res = es_runner.invoke(create_snapshot, ["tests", "--indices", "nomatch-xyz*"], obj=script_info)
    assert res.exit_code == 1
    assert "No index matches 'nomatch-xyz*'" in res.output


def test_snapshot_create_prefixed_indices(script_info, app, es_runner, monkeypatch, new_index_name1):
    """Create captures the prefixed indices of the instance and the global state."""
    monkeypatch.setitem(app.config, "SEARCH_INDEX_PREFIX", "records-")
    current_search_client.indices.create(index=new_index_name1, body={})
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = es_runner.invoke(create_snapshot, ["tests", "--name", "20260917_0900"], obj=script_info)
    assert res.exit_code == 0
    assert "Snapshot '20260917_0900': 1 indices matching 'records-*'." in res.output
    assert captured["create"]["body"] == {"indices": "records-*", "include_global_state": True}
    assert captured["create"]["request_timeout"] is None


def test_snapshot_create_names_the_snapshot_it_started(script_info, app, es_runner, monkeypatch, new_index_name1):
    """Without --wait the name must still be reported, the CLI invents it."""
    current_search_client.indices.create(index=new_index_name1, body={})
    _fake_snapshot_client(monkeypatch, {})

    res = es_runner.invoke(create_snapshot, ["tests"], obj=script_info)
    assert res.exit_code == 0
    started = next(line for line in res.output.splitlines() if "started" in line)
    assert re.fullmatch(
        r"Snapshot '(\d{4}\.\d{2}\.\d{2}_\d{2}:\d{2}:\d{2})' started\. "
        r"Follow it with: snapshot list tests -n \1",
        started,
    )


def test_snapshot_create_wait_raises_the_read_timeout(script_info, app, es_runner, monkeypatch, new_index_name1):
    """--wait must outlive the 10s the client would otherwise give up after."""
    current_search_client.indices.create(index=new_index_name1, body={})
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = es_runner.invoke(create_snapshot, ["tests", "--wait"], obj=script_info)
    assert res.exit_code == 0
    assert captured["create"]["request_timeout"] == WAIT_REQUEST_TIMEOUT


def test_snapshot_create_failure_exits(script_info, app, es_runner, new_index_name1):
    """A failing snapshot reports the error and exits non-zero."""
    current_search_client.indices.create(index=new_index_name1, body={})
    res = es_runner.invoke(create_snapshot, ["nosuchrepository"], obj=script_info)
    assert res.exit_code == 1
    assert "ERROR SNAPSHOT" in res.output


def test_snapshot_create_duplicate_name(script_info, app, es_runner, monkeypatch, new_index_name1):
    """A name already taken tells how to get out of it."""
    current_search_client.indices.create(index=new_index_name1, body={})
    error = RequestError(400, "invalid_snapshot_name_exception", {})
    _fake_snapshot_client(monkeypatch, {}, error=error)

    res = es_runner.invoke(create_snapshot, ["tests", "--name", "20260916_1544"], obj=script_info)
    assert res.exit_code == 1
    assert "Delete '20260916_1544' first, or pick another name" in res.output


def test_snapshot_restore_reopens_on_failure(script_info, app, es_runner, monkeypatch, new_index_name1):
    """A failed restore must not leave the cluster closed."""
    current_search_client.indices.create(index=new_index_name1, body={})
    captured = {}
    _fake_snapshot_client(monkeypatch, captured, restore_error=RequestError(400, "snapshot_restore_exception", {}))

    res = es_runner.invoke(restore_snapshot, ["tests", "snap", "--yes-i-know"], obj=script_info)
    assert res.exit_code == 1
    assert "reopening all indices" in res.output
    assert captured["open"] == "*"


def test_snapshot_restore_deletes_instance_indices(script_info, app, es_runner, monkeypatch):
    """Restore --delete drops the instance indices and leaves the global state alone."""
    monkeypatch.setitem(app.config, "SEARCH_INDEX_PREFIX", "records-")
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = es_runner.invoke(
        restore_snapshot,
        ["tests", "snap", "--delete", "--yes-i-know"],
        input="y\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    assert captured["delete"] == "records-*"
    assert captured["restore"]["body"] == {"include_global_state": False}


def test_cli_es_snapshots(script_info, app, es_runner, new_index_name1):
    """Test snapshot lifecycle command line interface."""
    runner = es_runner
    current_search_client.indices.create(index=new_index_name1, body={})

    res = runner.invoke(create_repository, ["tests", "snap"], obj=script_info)
    if res.exit_code != 0:
        pytest.skip("cluster started without path.repo: snapshot repositories cannot be registered")

    res = runner.invoke(create_snapshot, ["test"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(list_snapshot, ["tests"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(restore_snapshot, ["snap", "test", "--yes-i-know"], input="y\n", obj=script_info)

    assert res.exit_code == 0
    res = runner.invoke(delete_snapshot, ["snap", "test", "--yes-i-know"], obj=script_info)
    assert res.exit_code == 0
