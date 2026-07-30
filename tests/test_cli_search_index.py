# RERO Invenio Base
# Copyright (C) 2025 RERO.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Test cli search index commands."""

from datetime import UTC, datetime
from unittest.mock import MagicMock, patch

from invenio_search import current_search, current_search_client
from opensearchpy.exceptions import OpenSearchException

from rero_invenio_base.cli.search.index import (
    close_index,
    info,
    move_index,
    open_index,
    rebuild_index,
    reindex,
    switch_index,
)


def test_cli_search_reindex(app, es_runner):
    """Test reindex command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.current_search_client") as mock_client:
        mock_client.reindex = MagicMock(return_value={"task": "task_123"})
        res = runner.invoke(reindex, ["source_index", "dest_index"], obj=app)
        assert res.exit_code == 0
        assert "task_123" in res.output


def test_cli_search_open_index(app, es_runner):
    """Test open index command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.Index") as mock_index:
        mock_index.return_value.open.return_value = {"acknowledged": True}
        res = runner.invoke(open_index, [], obj=app)
        assert res.exit_code == 0


def test_cli_search_open_index_error(app, es_runner):
    """Test open index command with error."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.Index") as mock_index:
        mock_index.return_value.open.side_effect = OpenSearchException("Cannot open index")
        res = runner.invoke(open_index, ["-i", "test_index"], obj=app)
        assert res.exit_code == 0  # Error is caught and displayed


def test_cli_search_close_index(app, es_runner):
    """Test close index command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.Index") as mock_index:
        mock_index.return_value.close.return_value = {"acknowledged": True}
        res = runner.invoke(close_index, [], obj=app)
        assert res.exit_code == 0


def test_cli_search_close_index_error(app, es_runner):
    """Test close index command with error."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.Index") as mock_index:
        mock_index.return_value.close.side_effect = OpenSearchException("Cannot close index")
        res = runner.invoke(close_index, ["-i", "test_index"], obj=app)
        assert res.exit_code == 0  # Error is caught and displayed


def test_cli_search_info(app, es_runner):
    """Test info command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.current_search_client") as mock_client:
        mock_client.indices.get = MagicMock(
            return_value={"test_index": {"aliases": {}, "mappings": {}, "settings": {}}}
        )
        res = runner.invoke(info, ["-i", "test"], obj=app)
        assert res.exit_code == 0


def test_cli_search_info_with_options(app, es_runner):
    """Test info command with display options."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.index.current_search_client") as mock_client:
        mock_client.indices.get = MagicMock(
            return_value={
                "test_index": {"aliases": {"test": {}}, "mappings": {"properties": {}}, "settings": {"index": {}}}
            }
        )
        res = runner.invoke(info, ["-i", "test", "-a", "-m", "-s"], obj=app)
        assert res.exit_code == 0


def test_cli_search_move_index_error_create(app, es_runner):
    """Test move index exits 1 when the destination index cannot be created.

    ``new=MagicMock()`` is required: the Invenio proxies expose ``__await__``, so a
    bare ``patch()`` autodetects them as awaitable and installs an ``AsyncMock``
    whose children return coroutines instead of the configured values.
    """
    runner = es_runner

    with (
        patch("rero_invenio_base.cli.search.index.current_search_client", new=MagicMock()) as mock_client,
        patch("rero_invenio_base.cli.search.index.current_search", new=MagicMock()) as mock_search,
    ):
        mock_search.put_templates.return_value = []
        mock_search.aliases.get.return_value = {"test": "mapping.json"}
        mock_client.indices.create.side_effect = Exception("Create failed")

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "{}"
            res = runner.invoke(move_index, ["records", "old_index", "new_index", "-n", "0"], obj=app)
            assert res.exit_code == 1
            assert "ERROR CREATE: Create failed" in res.output


def test_cli_search_move_index_error_reindex(app, es_runner):
    """Test move index exits 2 when the reindex task reports failures."""
    runner = es_runner

    with (
        patch("rero_invenio_base.cli.search.index.current_search_client", new=MagicMock()) as mock_client,
        patch("rero_invenio_base.cli.search.index.current_search", new=MagicMock()) as mock_search,
        patch("builtins.open", create=True) as mock_open,
    ):
        mock_search.aliases.get.return_value = {"test": "mapping.json"}
        mock_open.return_value.__enter__.return_value.read.return_value = '{"mappings": {}}'
        mock_client.reindex.return_value = {"task": "task-1"}
        mock_client.tasks.get.return_value = {"completed": True, "response": {"failures": ["boom"]}}

        res = runner.invoke(move_index, ["records", "old-index", "new-index", "--no-templates"], obj=app)

        assert res.exit_code == 2
        assert "ERROR REINDEX" in res.output
        # The create stage ran against the mocked client, never the real cluster.
        mock_client.indices.create.assert_called_once()
        assert not current_search_client.indices.exists(index="new-index")


def test_cli_search_move_index_error_switch(app, es_runner):
    """Test move index exits 3 when the alias switch fails."""
    runner = es_runner

    with (
        patch("rero_invenio_base.cli.search.index.current_search_client", new=MagicMock()) as mock_client,
        patch("rero_invenio_base.cli.search.index.current_search", new=MagicMock()) as mock_search,
        patch("builtins.open", create=True) as mock_open,
    ):
        mock_search.aliases.get.return_value = {"test": "mapping.json"}
        mock_open.return_value.__enter__.return_value.read.return_value = '{"mappings": {}}'
        mock_client.reindex.return_value = {"task": "task-1"}
        mock_client.tasks.get.return_value = {"completed": True, "response": {}}
        mock_client.indices.get_alias.side_effect = Exception("Switch failed")

        res = runner.invoke(move_index, ["records", "old-index", "new-index", "--no-templates"], obj=app)

        assert res.exit_code == 3
        assert "ERROR SWITCH: Switch failed" in res.output
        assert not current_search_client.indices.exists(index="new-index")


# Integration tests using real OpenSearch instance


def test_cli_search_info_real_index(app, es_runner, new_index_name1):
    """Test info command with real OpenSearch index."""
    runner = es_runner

    # Create a real index
    current_search_client.indices.create(
        index=new_index_name1,
        body={"settings": {"number_of_shards": 1}, "mappings": {"properties": {"title": {"type": "text"}}}},
    )

    # Test info command
    res = runner.invoke(info, ["-i", new_index_name1], obj=app)
    assert res.exit_code == 0
    assert new_index_name1 in res.output

    # Test with all options
    res = runner.invoke(info, ["-i", new_index_name1, "-a", "-m", "-s"], obj=app)
    assert res.exit_code == 0
    assert "aliases" in res.output
    assert "mappings" in res.output or "properties" in res.output
    assert "settings" in res.output


def test_cli_search_open_close_real_index(app, es_runner, new_index_name1):
    """Test open and close commands with real OpenSearch index."""
    runner = es_runner

    # Create a real index
    current_search_client.indices.create(
        index=new_index_name1,
        body={"settings": {"number_of_shards": 1}},
    )

    # Close the index
    res = runner.invoke(close_index, ["-i", new_index_name1], obj=app)
    assert res.exit_code == 0

    # Verify it's closed by checking index status
    status = current_search_client.indices.get(new_index_name1)
    assert status[new_index_name1]["settings"]["index"]["verified_before_close"] == "true"

    # Open the index
    res = runner.invoke(open_index, ["-i", new_index_name1], obj=app)
    assert res.exit_code == 0


def test_cli_search_switch_index_real(app, es_runner, new_index_name1, new_index_name2):
    """Test switch command with real OpenSearch indices."""
    runner = es_runner

    # Create two real indices
    current_search_client.indices.create(index=new_index_name1, body={"settings": {"number_of_shards": 1}})
    current_search_client.indices.create(index=new_index_name2, body={"settings": {"number_of_shards": 1}})

    # Add alias to the first index
    test_alias = "test-alias"
    current_search_client.indices.put_alias(index=new_index_name1, name=test_alias)

    # Switch alias to the second index
    res = runner.invoke(switch_index, [new_index_name1, new_index_name2], obj=app)
    assert res.exit_code == 0
    assert "Successfully switched" in res.output

    # Verify alias moved
    aliases = current_search_client.indices.get_alias(name=test_alias)
    assert new_index_name2 in aliases
    assert new_index_name1 not in aliases


def _old_index():
    """Return a fixed past-dated index name for rebuild tests."""
    return "records-record-v1.0.0-20250101"


def _new_index():
    """Return the index name rebuild would create today."""
    registered = next(iter(current_search.aliases.get("records")))
    return f"{registered}-{datetime.now(UTC).strftime('%Y%m%d')}"


def test_rebuild_index_unknown_resource(rebuild_runner, app):
    """Rebuild exits 1 for an unknown alias."""
    res = rebuild_runner.invoke(rebuild_index, ["nonexistent"], obj=app)
    assert res.exit_code == 1
    assert "Unknown resource" in res.output


def test_rebuild_index_fresh(rebuild_runner, app):
    """Rebuild creates a fresh index and registers the alias when none exist."""
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=app)
    assert res.exit_code == 0
    assert current_search_client.indices.exists_alias(name="records")


def test_rebuild_index_fresh_new_index_already_exists(rebuild_runner, app):
    """Rebuild exits 1 when the target index exists but the alias is missing."""
    current_search_client.indices.create(index=_new_index(), body={})
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=app)
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_rebuild_index_noop(rebuild_runner, app):
    """Rebuild is a no-op when the alias already points to today's index."""
    today_index = _new_index()
    current_search_client.indices.create(index=today_index, body={})
    current_search_client.indices.put_alias(index=today_index, name="records")
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=app)
    assert res.exit_code == 0
    assert "Nothing to do" in res.output


def test_rebuild_index_new_already_exists(rebuild_runner, app):
    """Rebuild exits 1 when the new index already exists and the alias points elsewhere."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    current_search_client.indices.create(index=_new_index(), body={})
    res = rebuild_runner.invoke(rebuild_index, ["records", "--no-templates"], obj=app)
    assert res.exit_code == 1
    assert "already exists" in res.output


def test_rebuild_index_normal_confirm(rebuild_runner, app):
    """Rebuild switches alias and deletes old index when confirmed."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--interval", "0"],
        input="y\n",
        obj=app,
    )
    assert res.exit_code == 0
    assert not current_search_client.indices.exists(index=old)
    assert current_search_client.indices.exists(index=_new_index())
    assert current_search_client.indices.exists_alias(name="records")


def test_rebuild_index_normal_abort(rebuild_runner, app):
    """Rebuild leaves cluster unchanged when the user declines the confirmation."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--interval", "0"],
        input="n\n",
        obj=app,
    )
    assert res.exit_code == 0
    assert current_search_client.indices.exists(index=old)
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == [old]


def test_rebuild_index_inplace(rebuild_runner, app):
    """--inplace rebuilds under the same name: alias returns to old, temp deleted."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--inplace", "--interval", "0"],
        input="y\ny\n",
        obj=app,
    )
    assert res.exit_code == 0
    assert current_search_client.indices.exists(index=old)
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == [old]
    temp_indices = list(current_search_client.indices.get(f"{old}-tmp-*").keys())
    assert not temp_indices


def test_rebuild_index_inplace_abort_second_confirm(rebuild_runner, app):
    """--inplace abort at final confirm: alias stays on temp, old index recreated but not live."""
    old = _old_index()
    current_search_client.indices.create(index=old, body={})
    current_search_client.indices.put_alias(index=old, name="records")
    res = rebuild_runner.invoke(
        rebuild_index,
        ["records", "--no-templates", "--inplace", "--interval", "0"],
        input="y\nn\n",
        obj=app,
    )
    assert res.exit_code == 0
    temp_indices = list(current_search_client.indices.get(f"{old}-tmp-*").keys())
    assert len(temp_indices) == 1
    alias_targets = list(current_search_client.indices.get_alias(name="records").keys())
    assert alias_targets == temp_indices
    assert current_search_client.indices.exists(index=old)
