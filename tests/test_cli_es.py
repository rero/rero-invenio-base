# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli elasticsearch commands."""

from datetime import UTC, datetime

from invenio_search import current_search, current_search_client

from rero_invenio_base.cli.es.alias import delete_alias, get_alias, put_alias
from rero_invenio_base.cli.es.index import (
    close_index,
    create_index,
    open_index,
    rebuild_index,
    switch_index,
    update_mapping,
)
from rero_invenio_base.cli.es.snapshot.cli import (
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


def test_cli_es_snapshot_repository(script_info, app, es_runner, new_index_name1):
    """Test snapshot repository command line interface."""
    runner = es_runner

    res = runner.invoke(create_repository, ["tests", "snap"], obj=script_info)
    assert res.exit_code == 0

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
        ["records", "--no-templates", "--interval", "0"],
        input="y\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    assert not current_search_client.indices.exists(index=old)
    assert current_search_client.indices.exists(index=_new_index())
    assert current_search_client.indices.exists_alias(name="records")


def test_rebuild_index_normal_abort(rebuild_runner, script_info):
    """Rebuild leaves cluster unchanged when the user declines the confirmation."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--interval", "0"],
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
        ["records", "--no-templates", "--inplace", "--interval", "0"],
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
        ["records", "--no-templates", "--inplace", "--interval", "0"],
        input="y\nn\n",
        obj=script_info,
    )
    assert res.exit_code == 0
    temp_indices = list(current_search_client.indices.get(f"{old}-tmp-*").keys())
    assert len(temp_indices) == 1
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == temp_indices
    assert current_search_client.indices.exists(index=old)


def test_cli_es_snapshots(script_info, app, es_runner, new_index_name1):
    """Test snapshot lifecycle command line interface."""
    runner = es_runner

    res = runner.invoke(create_repository, ["tests", "snap"], obj=script_info)

    res = runner.invoke(create_snapshot, ["test"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(list_snapshot, ["tests"], obj=script_info)
    assert res.exit_code == 0

    res = runner.invoke(restore_snapshot, ["snap", "test", "--yes-i-know"], input="y\n", obj=script_info)

    assert res.exit_code == 0
    res = runner.invoke(delete_snapshot, ["snap", "test", "--yes-i-know"], obj=script_info)
    assert res.exit_code == 0
