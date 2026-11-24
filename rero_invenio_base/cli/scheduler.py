# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click scheduler command-line utilities."""

import click
from flask.cli import with_appcontext

from ..modules.scheduler import current_scheduler


@click.group()
def scheduler():
    """Manage the scheduled tasks."""


@scheduler.command()
@with_appcontext
def info():
    """Display the scheduled tasks."""
    click.secho("Scheduled tasks:", fg="green")
    click.echo("\n".join(current_scheduler.display_all()))


@scheduler.command()
@click.option("-r", "--reset", "reset", is_flag=True, default=False, help="Remove the stored tasks first.")
@click.option("-v", "--verbose", "verbose", is_flag=True, default=False)
@with_appcontext
def init(reset, verbose):
    """Store the scheduled tasks of the configuration in the database."""
    if reset:
        click.secho("Reset DB scheduler!", fg="red", bold=True)
        current_scheduler.reset()
    else:
        click.secho("Initalize DB scheduler!", fg="yellow")
    current_scheduler.setup_schedule()
    if verbose:
        click.echo("\n".join(current_scheduler.display_all()))


@scheduler.command()
@click.option("-a", "--all", "all_", is_flag=True, default=False, help="Change all the tasks.")
@click.option("-n", "--name", "names", multiple=True, default=None, help="Name of a task to change.")
@click.option("-d", "--disable", "disable", is_flag=True, default=False, help="Switch the tasks off.")
@click.option("-v", "--verbose", "verbose", is_flag=True, default=False)
@with_appcontext
def enable_tasks(all_, names, disable, verbose):
    """Switch scheduled tasks on, or off with --disable."""
    if verbose:
        click.secho("Scheduler tasks enabled:", fg="green")
    if all_:
        current_scheduler.set_enable_all(not disable)
        if verbose:
            click.echo("\n".join(current_scheduler.display_all()))
        return
    for name in names:
        name = name.strip()
        current_scheduler.set_entry_enabled(name=name, enable=not disable)
        # An unknown name changes nothing, so it is always reported.
        if not (entry := current_scheduler.get(name=name)):
            click.secho(f"Not found entry: {name}", fg="red")
        elif verbose:
            click.echo(current_scheduler.display_entry(entry=entry))
