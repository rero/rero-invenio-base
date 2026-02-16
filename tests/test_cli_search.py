# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli search commands."""

from invenio_search import current_search_client

from rero_invenio_base.cli.search.alias import delete_alias, get_alias, put_alias
from rero_invenio_base.cli.search.index import (
    close_index,
    create_index,
    open_index,
    switch_index,
    update_mapping,
)
from rero_invenio_base.cli.search.snapshot.cli import (
    create_snapshot,
    delete_snapshot,
    list_snapshot,
    restore_snapshot,
)
from rero_invenio_base.cli.search.snapshot.repository import (
    create_repository,
    delete_repository,
    list_repository,
)


def test_cli_search_index_alias(app, es_runner, new_index_name1, new_index_name2):
    """Test index and aliases command line interface."""
    runner = es_runner

    res = runner.invoke(create_index, ["records", new_index_name1], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(put_alias, [new_index_name1, "records"], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(get_alias, [], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(update_mapping, ["-a", "records"], obj=app)
    assert res.exit_code == 0

    # Target the test index explicitly: the default is `*`, which would close and
    # reopen every index on the cluster, including system indices.
    res = runner.invoke(close_index, ["--index", new_index_name1], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(open_index, ["--index", new_index_name1], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(create_index, ["records", new_index_name2], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(switch_index, [new_index_name1, new_index_name2], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(get_alias, [], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(delete_alias, [new_index_name2, "records", "--yes-i-know"], obj=app)
    assert res.exit_code == 0


def test_cli_search_snapshot_repository(app, es_runner, tmp_path):
    """Test snapshot repository command line interface.

    The location is relative to the node's ``path.repo``; ``tmp_path`` only
    supplies a name unique to this test.
    """
    runner = es_runner

    res = runner.invoke(create_repository, ["tests", tmp_path.name], obj=app)
    assert res.exit_code == 0
    assert "acknowledged" in res.output

    res = runner.invoke(list_repository, [], obj=app)
    assert res.exit_code == 0
    assert "tests" in res.output

    res = runner.invoke(delete_repository, ["tests", "--yes-i-know"], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(list_repository, [], obj=app)
    assert res.exit_code == 0
    assert "tests" not in res.output


def test_cli_search_snapshots(app, es_runner, snapshot_repository, new_index_name1):
    """Test snapshot lifecycle command line interface."""
    runner = es_runner
    repository = snapshot_repository

    # Give the snapshot something to capture.
    res = runner.invoke(create_index, ["records", new_index_name1], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(create_snapshot, [repository, "-n", "snap1", "-w"], obj=app)
    assert res.exit_code == 0
    assert "SUCCESS" in res.output

    res = runner.invoke(list_snapshot, [repository], obj=app)
    assert res.exit_code == 0
    assert "snap1" in res.output

    res = runner.invoke(restore_snapshot, [repository, "snap1", "-w", "--delete", "--yes-i-know"], input="y\n", obj=app)
    assert res.exit_code == 0
    assert current_search_client.indices.exists(index=new_index_name1)

    res = runner.invoke(delete_snapshot, [repository, "snap1", "--yes-i-know"], obj=app)
    assert res.exit_code == 0

    res = runner.invoke(list_snapshot, [repository], obj=app)
    assert res.exit_code == 0
    assert "snap1" not in res.output
