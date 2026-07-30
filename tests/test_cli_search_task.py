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

"""Test cli search task commands."""

from unittest.mock import MagicMock, patch

from rero_invenio_base.cli.search.task import task_cancel, task_get, task_list, task_watch


def test_cli_search_task_list(app, es_runner):
    """Test task list command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.list = MagicMock(return_value={"nodes": {}})
        res = runner.invoke(task_list, [], obj=app)
        assert res.exit_code == 0


def test_cli_search_task_get_with_response(app, es_runner):
    """Test task get command with response."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.get = MagicMock(return_value={"response": {"acknowledged": True}})
        res = runner.invoke(task_get, ["test_task_id"], obj=app)
        assert res.exit_code == 0


def test_cli_search_task_get_with_task_info(app, es_runner):
    """Test task get command with task info."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.get = MagicMock(return_value={"task": {"description": "reindex", "status": {"created": 100}}})
        res = runner.invoke(task_get, ["test_task_id"], obj=app)
        assert res.exit_code == 0


def test_cli_search_task_get_error(app, es_runner):
    """Test task get command with error."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.get = MagicMock(side_effect=Exception("Task not found"))
        res = runner.invoke(task_get, ["invalid_task"], obj=app)
        assert res.exit_code == 1


def test_cli_search_task_cancel(app, es_runner):
    """Test task cancel command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.cancel = MagicMock(return_value={"nodes": {}})
        res = runner.invoke(task_cancel, ["test_task", "--yes-i-know"], obj=app)
        assert res.exit_code == 0


def test_cli_search_task_cancel_error(app, es_runner):
    """Test task cancel command with error."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.cancel = MagicMock(side_effect=Exception("Cannot cancel task"))
        res = runner.invoke(task_cancel, ["test_task", "--yes-i-know"], obj=app)
        assert res.exit_code == 1


def test_cli_search_task_watch(app, es_runner):
    """Test task watch command."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        # First call: task running, second call: task completed
        mock_client.tasks.get = MagicMock(
            side_effect=[
                {"completed": False, "task": {"description": "reindex", "status": {"created": 50}}},
                {"completed": True, "response": {"created": 100}},
            ]
        )
        with patch("rero_invenio_base.cli.search.task.sleep"):
            res = runner.invoke(task_watch, ["test_task", "-n", "0"], obj=app)
            assert res.exit_code == 0


def test_cli_search_task_watch_error(app, es_runner):
    """Test task watch command with error."""
    runner = es_runner

    with patch("rero_invenio_base.cli.search.task.current_search_client") as mock_client:
        mock_client.tasks.get = MagicMock(side_effect=Exception("Task error"))
        res = runner.invoke(task_watch, ["test_task"], obj=app)
        assert res.exit_code == 1
