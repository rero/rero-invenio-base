# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli utils commands."""

from os.path import dirname, join

from click.testing import CliRunner

from rero_invenio_base.cli.utils import check_json


def test_cli_validate(script_info):
    """Test JOSON indentation cli."""
    runner = CliRunner()
    file_name = join(dirname(__file__), "./data/data.json")

    res = runner.invoke(check_json, [file_name], obj=script_info)
    assert res.exit_code == 0

    file_name = join(dirname(__file__), "./data/data_bad_indentation.json")

    res = runner.invoke(check_json, [file_name], obj=script_info)
    assert res.exit_code == 1
