# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli search snapshot commands."""

import re
import sys
from types import SimpleNamespace

import pytest
from invenio_search import current_search_client
from opensearchpy.exceptions import RequestError, TransportError

from rero_invenio_base.cli.search.snapshot.cli import WAIT_REQUEST_TIMEOUT, create_snapshot, restore_snapshot
from rero_invenio_base.cli.search.snapshot.repository import create_repository, delete_repository, list_repository


def _fake_snapshot_client(monkeypatch, captured, error=None, restore_error=None):
    """Keep the real cat API but capture the snapshot and indices calls."""

    def snapshot_create(repository, name, body=None, **kwargs):
        captured["create"] = {"repository": repository, "name": name, "body": body, **kwargs}
        if error:
            raise error
        return {"accepted": True}

    def snapshot_get(repository, name, **kwargs):
        return {"snapshots": [{"snapshot": name, "indices": []}]}

    def snapshot_restore(repository, name, body=None, **kwargs):
        captured["restore"] = {"repository": repository, "name": name, "body": body}
        if restore_error:
            raise restore_error
        return {"accepted": True}

    def indices_delete(index=None, **kwargs):
        captured["delete"] = index
        return {"acknowledged": True}

    def indices_close(index=None, **kwargs):
        captured.setdefault("close", []).append(index)
        return {"acknowledged": True}

    def indices_open(index=None, **kwargs):
        captured.setdefault("open", []).append(index)
        return {"acknowledged": True}

    snapshot_cli = sys.modules[create_snapshot.callback.__module__]
    monkeypatch.setattr(
        snapshot_cli,
        "current_search_client",
        SimpleNamespace(
            cat=current_search_client.cat,
            snapshot=SimpleNamespace(create=snapshot_create, get=snapshot_get, restore=snapshot_restore),
            indices=SimpleNamespace(delete=indices_delete, close=indices_close, open=indices_open),
        ),
    )


def test_snapshot_create_no_match(app, search_runner):
    """Create refuses to snapshot a pattern that matches no index."""
    res = search_runner.invoke(create_snapshot, ["tests", "--indices", "nomatch-xyz*"], obj=app)
    assert res.exit_code == 1
    assert "No index matches 'nomatch-xyz*'" in res.output


def test_snapshot_create_prefixed_indices(app, search_runner, monkeypatch, new_index_name1):
    """Create captures the prefixed indices of the instance and the global state."""
    monkeypatch.setitem(app.config, "SEARCH_INDEX_PREFIX", "records-")
    current_search_client.indices.create(index=new_index_name1, body={})
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = search_runner.invoke(create_snapshot, ["tests", "--name", "20260917_0900"], obj=app)
    assert res.exit_code == 0
    assert "Snapshot '20260917_0900': 1 indices matching 'records-*'." in res.output
    assert captured["create"]["body"] == {"indices": "records-*", "include_global_state": True}
    assert captured["create"]["request_timeout"] is None


def test_snapshot_create_names_the_snapshot_it_started(app, search_runner, monkeypatch, new_index_name1):
    """Without --wait the name must still be reported, the CLI invents it."""
    current_search_client.indices.create(index=new_index_name1, body={})
    _fake_snapshot_client(monkeypatch, {})

    res = search_runner.invoke(create_snapshot, ["tests"], obj=app)
    assert res.exit_code == 0
    started = next(line for line in res.output.splitlines() if "started" in line)
    assert re.fullmatch(
        r"Snapshot '(\d{4}\.\d{2}\.\d{2}_\d{2}:\d{2}:\d{2})' started\. "
        r"Follow it with: snapshot list tests -n \1",
        started,
    )


def test_snapshot_create_wait_raises_the_read_timeout(app, search_runner, monkeypatch, new_index_name1):
    """--wait must outlive the 10s the client would otherwise give up after."""
    current_search_client.indices.create(index=new_index_name1, body={})
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = search_runner.invoke(create_snapshot, ["tests", "--wait"], obj=app)
    assert res.exit_code == 0
    assert captured["create"]["request_timeout"] == WAIT_REQUEST_TIMEOUT


def test_snapshot_create_failure_exits(app, search_runner, new_index_name1):
    """A failing snapshot reports the error and exits non-zero."""
    current_search_client.indices.create(index=new_index_name1, body={})
    res = search_runner.invoke(create_snapshot, ["nosuchrepository"], obj=app)
    assert res.exit_code == 1
    assert "ERROR SNAPSHOT" in res.output


def test_snapshot_create_duplicate_name(app, search_runner, monkeypatch, new_index_name1):
    """A name already taken tells how to get out of it."""
    current_search_client.indices.create(index=new_index_name1, body={})
    error = RequestError(400, "invalid_snapshot_name_exception", {})
    _fake_snapshot_client(monkeypatch, {}, error=error)

    res = search_runner.invoke(create_snapshot, ["tests", "--name", "20260916_1544"], obj=app)
    assert res.exit_code == 1
    assert "Delete '20260916_1544' first, or pick another name" in res.output


def test_snapshot_restore_reopens_on_failure(app, search_runner, monkeypatch, new_index_name1, new_index_name2):
    """A failed restore reopens what it closed, and only that."""
    for name in (new_index_name1, new_index_name2):
        current_search_client.indices.create(index=name, body={})
    current_search_client.indices.close(index=new_index_name2)
    captured = {}
    _fake_snapshot_client(monkeypatch, captured, restore_error=RequestError(400, "snapshot_restore_exception", {}))

    res = search_runner.invoke(restore_snapshot, ["tests", "snap", "--yes-i-know"], obj=app)
    assert res.exit_code == 1
    assert "reopening the indices" in res.output
    assert captured["open"] == ["*"]
    assert captured["close"] == ["*", new_index_name2]


def test_snapshot_restore_keeps_closed_indices_closed(
    app, search_runner, snapshot_repository, new_index_name1, new_index_name2
):
    """Restore reopens the indices it closed, but not those closed before it and not restored."""
    for name in (new_index_name1, new_index_name2):
        current_search_client.indices.create(index=name, body={})
    current_search_client.snapshot.create(
        snapshot_repository, "snap", body={"indices": new_index_name1}, wait_for_completion=True
    )
    # both closed beforehand: the first comes back with the restore, the second is left alone.
    current_search_client.indices.close(index=f"{new_index_name1},{new_index_name2}")

    res = search_runner.invoke(restore_snapshot, [snapshot_repository, "snap", "--wait", "--yes-i-know"], obj=app)
    assert res.exit_code == 0, res.output
    assert f"Closed again, as before the restore: {new_index_name2}." in res.output
    indices = current_search_client.cat.indices(index="records-*", h="index,status", format="json")
    assert {idx["index"]: idx["status"] for idx in indices} == {new_index_name1: "open", new_index_name2: "close"}


def test_snapshot_restore_unknown_snapshot(app, search_runner, snapshot_repository, new_index_name1):
    """A wrong snapshot name fails before any index is closed."""
    current_search_client.indices.create(index=new_index_name1, body={})
    res = search_runner.invoke(restore_snapshot, [snapshot_repository, "missing", "--yes-i-know"], obj=app)
    assert res.exit_code == 1
    assert "All indices are closed." not in res.output
    (status,) = current_search_client.cat.indices(index=new_index_name1, h="status", format="json")
    assert status["status"] == "open"


@pytest.mark.parametrize(
    ("command", "args"),
    [(list_repository, []), (create_repository, ["tests", "/backup"]), (delete_repository, ["tests", "--yes-i-know"])],
    ids=["list", "create", "delete"],
)
def test_repository_command_errors_exit_1(app, search_runner, monkeypatch, command, args):
    """A failing repository call is reported and exits 1."""

    def fail(*args, **kwargs):
        raise TransportError(500, "repository_exception", {})

    repository_cli = sys.modules[command.callback.__module__]
    snapshot = SimpleNamespace(get_repository=fail, create_repository=fail, delete_repository=fail)
    monkeypatch.setattr(repository_cli, "current_search_client", SimpleNamespace(snapshot=snapshot))
    res = search_runner.invoke(command, args, obj=app)
    assert res.exit_code == 1
    assert "repository_exception" in res.output


def test_snapshot_restore_deletes_instance_indices(app, search_runner, monkeypatch):
    """Restore --delete drops the instance indices and leaves the global state alone."""
    monkeypatch.setitem(app.config, "SEARCH_INDEX_PREFIX", "records-")
    captured = {}
    _fake_snapshot_client(monkeypatch, captured)

    res = search_runner.invoke(
        restore_snapshot,
        ["tests", "snap", "--delete", "--yes-i-know"],
        input="y\n",
        obj=app,
    )
    assert res.exit_code == 0
    assert captured["delete"] == "records-*"
    assert captured["restore"]["body"] == {"include_global_state": False}
