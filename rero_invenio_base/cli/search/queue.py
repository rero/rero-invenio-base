# RERO Invenio Base
# Copyright (C) 2025 RERO.
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

"""Click Celery queue command-line utilities."""

import json

import click
from celery import current_app as celery_app
from flask.cli import with_appcontext

from ..shared import abort_if_false


@click.group()
def queue():
    """Celery queue commands."""


@queue.command("list")
@with_appcontext
@click.option(
    "-t",
    "--timeout",
    default=5.0,
    type=float,
    help="Worker inspect timeout in seconds.",
)
def queue_list(timeout):
    """List Celery workers with their active, reserved, and scheduled task counts."""
    inspect = celery_app.control.inspect(timeout=timeout)
    stats = inspect.stats() or {}
    if not stats:
        click.secho(f"No workers responded within {timeout}s.", fg="yellow")
        return

    active = inspect.active() or {}
    reserved = inspect.reserved() or {}
    scheduled = inspect.scheduled() or {}

    click.secho(
        f"  {'WORKER':<44}  {'ACTIVE':>6}  {'RESERVED':>8}  {'SCHEDULED':>9}",
        bold=True,
    )
    for worker in sorted(stats):
        n_active = len(active.get(worker, []))
        n_reserved = len(reserved.get(worker, []))
        n_scheduled = len(scheduled.get(worker, []))
        color = "green" if (n_active or n_reserved) else None
        click.secho(
            f"  {worker:<44}  {n_active:>6}  {n_reserved:>8}  {n_scheduled:>9}",
            fg=color,
        )

    # Queue depths via broker connection (works for Redis and AMQP)
    try:
        queue_names = {celery_app.conf.task_default_queue or "celery"}
        for q in celery_app.conf.task_queues or []:
            queue_names.add(q.name if hasattr(q, "name") else str(q))

        click.secho(f"\n  {'QUEUE':<30}  {'DEPTH':>6}", bold=True)
        with celery_app.connection() as conn:
            for q_name in sorted(queue_names):
                try:
                    depth = conn.default_channel.queue_declare(q_name, passive=True).message_count
                except Exception:
                    depth = "?"
                color = "yellow" if depth and depth != "?" and depth > 0 else None
                click.secho(f"  {q_name:<30}  {depth!s:>6}", fg=color)
    except Exception as err:
        click.secho(f"\nCould not read queue depths: {err}", fg="yellow")


@queue.command("stats")
@with_appcontext
@click.option(
    "-t",
    "--timeout",
    default=5.0,
    type=float,
    help="Worker inspect timeout in seconds.",
)
def queue_stats(timeout):
    """Show detailed Celery worker statistics as JSON."""
    stats = celery_app.control.inspect(timeout=timeout).stats() or {}
    if not stats:
        click.secho(f"No workers responded within {timeout}s.", fg="yellow")
        return
    click.secho(json.dumps(stats, indent=2, default=str), fg="green")


@queue.command("purge")
@with_appcontext
@click.argument("queue_name", default="celery")
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to purge this queue?",
)
def queue_purge(queue_name):
    """Purge all pending tasks from a named queue.

    :param queue_name: name of the queue to purge (default: celery).
    """
    try:
        with celery_app.connection() as conn:
            n = conn.default_channel.queue_purge(queue_name)
        click.secho(f"Purged {n} task(s) from '{queue_name}'.", fg="yellow")
    except Exception as err:
        click.secho(f"Error: {err}", fg="red")
