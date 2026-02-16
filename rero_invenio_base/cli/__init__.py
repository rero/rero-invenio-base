# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click command-line utilities."""

import click

from .search import search
from .utils import utils


@click.group()
def rero():
    """RERO management commands."""


rero.add_command(utils)
rero.add_command(search)

__all__ = ["rero"]
