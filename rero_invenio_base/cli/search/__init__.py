# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search command-line utilities."""

import click

from .alias import alias
from .health import health
from .index import index
from .queue import queue
from .snapshot import snapshot
from .task import task


@click.group()
def search():
    """Search management commands."""


search.add_command(alias)
search.add_command(health)
search.add_command(index)
search.add_command(queue)
search.add_command(snapshot)
search.add_command(task)

__all__ = ["search"]
