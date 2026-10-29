# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click command-line utilities."""

import click

from .batch import batch
from .health import health
from .queue import queue
from .search import search
from .utils import utils


@click.group()
def rero():
    """RERO management commands."""


rero.add_command(batch)
rero.add_command(health)
rero.add_command(queue)
rero.add_command(utils)
rero.add_command(search)

__all__ = ["rero"]
