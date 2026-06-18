# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click command-line utilities."""

import click

from .es import es
from .utils import utils


@click.group()
def rero():
    """RERO management commands."""


rero.add_command(utils)
rero.add_command(es)

__all__ = "rero"
