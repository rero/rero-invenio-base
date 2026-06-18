# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click elasticsearch command-line utilities."""

import click

from .alias import alias
from .index import index
from .slm import slm
from .snapshot import snapshot
from .task import task


@click.group()
def es():
    """Elasticsarch management commands."""


es.add_command(index)
es.add_command(alias)
es.add_command(slm)
es.add_command(snapshot)
es.add_command(task)

__all__ = "index"
