# -*- coding: utf-8 -*-
#
# RERO Invenio Base
# Copyright (C) 2022 RERO.
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

"""Test cli elasticsearch commands."""

from click.testing import CliRunner
from invenio_search import current_search_client

from rero_invenio_base.cli.es.alias import delete_alias, get_alias, put_alias
from rero_invenio_base.cli.es.index import close_index, create_index, \
    open_index, switch_index, update_mapping


def test_cli_es_create(script_info, app, es):
    """Test JOSON indentation cli."""
    new_index_name1 = 'records-record-v1.0.0'
    new_index_name2 = 'records-2'
    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )
    search = app.extensions['invenio-search']
    search.register_mappings('records', 'mock_modules.mappings')

    runner = CliRunner()

    res = runner.invoke(
        create_index,
        ['records', new_index_name1],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        put_alias,
        [new_index_name1, 'records'],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        get_alias,
        [],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        update_mapping,
        ['-a', 'records'],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        close_index,
        [],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        open_index,
        [],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        create_index,
        ['records', new_index_name2],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        switch_index,
        [new_index_name1, new_index_name2],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        get_alias,
        [],
        obj=script_info
    )
    assert res.exit_code == 0

    res = runner.invoke(
        delete_alias,
        [new_index_name2, 'records', '--yes-i-know'],
        obj=script_info
    )
    assert res.exit_code == 0

    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )
