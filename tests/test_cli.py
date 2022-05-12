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

"""Test cli."""

from os.path import dirname, join

from click.testing import CliRunner

from rero_invenio_base.cli.utils import check_json, check_license


def test_cli_validate(script_info):
    """Test JOSON indentation cli."""
    runner = CliRunner()
    file_name = join(dirname(__file__), './data/data.json')

    res = runner.invoke(
        check_json,
        [file_name],
        obj=script_info
    )
    assert res.exit_code == 0

    file_name = join(dirname(__file__), './data/data_bad_indentation.json')

    res = runner.invoke(
        check_json,
        [file_name],
        obj=script_info
    )
    assert res.exit_code == 1


def test_cli_licence(script_info):
    """Test check license cli."""
    runner = CliRunner()
    cfg = join(dirname(__file__), '../check_license_config.yml')

    res = runner.invoke(
        check_license,
        [cfg],
        obj=script_info
    )
    assert res.exit_code == 0
