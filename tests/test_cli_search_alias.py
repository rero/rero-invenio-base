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

"""Test cli search alias commands."""

from invenio_search import current_search_client

from rero_invenio_base.cli.search.alias import delete_alias, get_alias, put_alias


def test_cli_search_get_alias_empty(app, es_runner):
    """Test get alias command with no aliases."""
    runner = es_runner
    res = runner.invoke(get_alias, [], obj=app)
    assert res.exit_code == 0


def test_cli_search_put_alias(app, es_runner, new_index_name1):
    """Test put alias command."""
    runner = es_runner
    # Create a test index first
    current_search_client.indices.create(index=new_index_name1, ignore=400)

    # Put an alias
    res = runner.invoke(put_alias, [new_index_name1, "test_alias"], obj=app)
    assert res.exit_code == 0

    # Verify alias was created
    aliases = current_search_client.indices.get_alias(index=new_index_name1)
    assert "test_alias" in aliases[new_index_name1]["aliases"]

    # Clean up
    current_search_client.indices.delete_alias(index=new_index_name1, name="test_alias", ignore=[400, 404])


def test_cli_search_delete_alias(app, es_runner, new_index_name1):
    """Test delete alias command."""
    runner = es_runner
    # Create a test index and alias first
    current_search_client.indices.create(index=new_index_name1, ignore=400)
    current_search_client.indices.put_alias(index=new_index_name1, name="test_alias_to_delete")

    # Delete the alias
    res = runner.invoke(delete_alias, [new_index_name1, "test_alias_to_delete", "--yes-i-know"], obj=app)
    assert res.exit_code == 0

    # Verify alias was deleted
    aliases = current_search_client.indices.get_alias(index=new_index_name1)
    assert "test_alias_to_delete" not in aliases[new_index_name1]["aliases"]
