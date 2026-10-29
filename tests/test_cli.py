# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the layout of the rero command group."""

import pytest
from click.testing import CliRunner

from rero_invenio_base.cli import rero


@pytest.mark.parametrize(
    "path",
    [["batch"], ["health"], ["queue"], ["utils", "check_json"], ["search", "index"]],
    ids=lambda path: " ".join(path),
)
def test_rero_command(path):
    """Each command is reachable under the rero group."""
    res = CliRunner().invoke(rero, [*path, "--help"])
    assert res.exit_code == 0, res.output


@pytest.mark.parametrize("name", ["health", "queue"])
def test_search_group_has_no_service_command(name):
    """Health and queue check more than Search, so they live at the root."""
    res = CliRunner().invoke(rero, ["search", name, "--help"])
    assert res.exit_code == 2
    assert f"No such command '{name}'" in res.output
