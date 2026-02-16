# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search tasks command-line utilities."""

import sys
from pprint import pformat
from time import sleep

import click
from invenio_search import current_search_client

try:
    from invenio_search.cli import es_version_check
except ImportError:
    from invenio_search.cli import search_version_check as es_version_check

from invenio_search.cli import with_appcontext

from ..shared import abort_if_false


@click.group()
def task():
    """Search task commands.

    See: https://opensearch.org/docs/latest/api-reference/tasks/
    """


@task.command("get")
@with_appcontext
@es_version_check
@click.argument("task")
def task_get(task):
    """Get task info.

    :param task: task id.
    """
    try:
        res = current_search_client.tasks.get(task)
        if info := res.get("response"):
            click.secho(f"{pformat(info)}", fg="green")
        elif info := res.get("task"):
            click.secho(f"{info.get('description')}", fg="yellow")
            click.secho(f"{pformat(info.get('status'))}", fg="yellow")
        else:
            click.secho(f"{pformat(res)}", fg="blue")
    except Exception as err:
        click.secho(f"Error: {err}", fg="red")
        sys.exit(1)


@task.command("list")
@with_appcontext
@es_version_check
def task_list():
    """Get task list."""
    res = current_search_client.tasks.list()
    click.secho(f"{pformat(res)}", fg="green")


@task.command("cancel")
@with_appcontext
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to cancel the task?",
)
@click.argument("task")
@es_version_check
def task_cancel(task):
    """Cancel task.

    :param task: task id.
    """
    try:
        res = current_search_client.tasks.cancel(task)
        click.secho(f"{pformat(res)}", fg="yellow")
    except Exception as err:
        click.secho(f"Error: {err}", fg="red")
        sys.exit(1)


@task.command("watch")
@with_appcontext
@es_version_check
@click.argument("task")
@click.option("-n", "--interval", default=1, type=int, help="seconds to wait between updates")
def task_watch(task, interval):
    """Watch task info.

    :param task: task id.
    :param interval: seconds to wait between updates.
    """
    click.secho(f"Watching task: {task}", fg="green")
    try:
        seconds = 0
        res = current_search_client.tasks.get(task)
        while not res.get("completed"):
            if info := res.get("task"):
                click.secho(f"Watching task: {task} {seconds} seconds ...", fg="green")
                click.secho(f"{info.get('description')}", fg="yellow")
                click.secho(f"{pformat(info.get('status'))}", fg="yellow")
            sleep(interval)
            seconds += interval
            res = current_search_client.tasks.get(task)

        click.secho(f"Finished task: {task} {seconds} seconds ...", fg="green")
        click.secho(f"{pformat(res.get('response'))}", fg="green")
    except Exception as err:
        click.secho(f"Error: {err}", fg="red")
        sys.exit(1)
