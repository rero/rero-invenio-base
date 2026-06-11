# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search snapshot command-line utilities."""

import json
from datetime import UTC, datetime

import click
from flask.cli import with_appcontext
from invenio_search import current_search, current_search_client

from ...shared import abort_if_false
from .repository import repository

_STATE_COLORS = {
    "SUCCESS": "green",
    "PARTIAL": "yellow",
    "FAILED": "red",
    "IN_PROGRESS": "blue",
}


def _print_snapshot_table(snapshots_list):
    """Render a condensed snapshot table to the terminal."""
    if not snapshots_list:
        click.secho("No snapshots found.", fg="yellow")
        return
    name_width = max(len(s["snapshot"]) for s in snapshots_list)
    click.secho(
        f"  {'SNAPSHOT':<{name_width}}  {'START TIME':<30}  {'DURATION':>10}  SHARDS   STATE",
        bold=True,
    )
    for snap in snapshots_list:
        state = snap["state"]
        shards = snap["shards"]
        shards_str = f"{shards.get('successful', 0)}/{shards.get('total', 0)}"
        line = (
            f"  {snap['snapshot']:<{name_width}}"
            f"  {snap['start_time']:<30}"
            f"  {snap['duration']:>9.1f}s"
            f"  {shards_str:<7}  "
        )
        click.echo(line, nl=False)
        click.secho(state, fg=_STATE_COLORS.get(state))


def _print_response(res):
    """Print an API response, using plain messages for simple acknowledgements."""
    if res.get("accepted"):
        click.secho("Accepted.", fg="green")
    elif res.get("acknowledged"):
        click.secho("Acknowledged.", fg="green")
    else:
        click.secho(json.dumps(res, indent=2), fg="green")


@click.group()
def snapshot():
    """SEARCH snapshot commands."""


snapshot.add_command(repository)


@snapshot.command("list")
@with_appcontext
@click.option("-n", "--name", default="_all", help="Snapshot name or pattern. Defaults to _all.")
@click.option("-N", "--names-only", is_flag=True, default=False, help="Print only snapshot names, one per line.")
@click.argument("repository")
def list_snapshot(repository, name, names_only):
    """List snapshots in a repository.

    When NAME is _all (the default), snapshots are shown as a formatted table.
    Pass a specific snapshot name to see its full details as JSON.
    """
    try:
        snapshots = current_search_client.snapshot.get(repository, name)
        if name == "_all":
            snap_list = [
                {
                    "snapshot": s["snapshot"],
                    "start_time": s["start_time"],
                    "duration": s["duration_in_millis"] / 1000,
                    "shards": s["shards"],
                    "state": s["state"],
                    "uuid": s["uuid"],
                }
                for s in snapshots["snapshots"]
            ]
            if names_only:
                for s in snap_list:
                    click.echo(s["snapshot"])
            else:
                _print_snapshot_table(snap_list)
        else:
            click.secho(json.dumps(snapshots, indent=2), fg="green")
    except Exception as err:
        click.secho(str(err), fg="red")


@snapshot.command("create")
@with_appcontext
@click.argument("repository")
@click.option(
    "-n",
    "--name",
    default=datetime.now(UTC).strftime("%Y.%m.%d_%H:%M:%S"),
    help="Snapshot name. Defaults to the current UTC timestamp (YYYY.MM.DD_HH:MM:SS).",
)
@click.option("-w", "--wait", is_flag=True, default=False, help="Wait for the snapshot to complete before returning.")
def create_snapshot(repository, name, wait):
    """Create a snapshot of all RERO ILS indices.

    Captures all indices registered in the application aliases plus
    events-stats-record-view*. Global cluster state is excluded.
    """
    indices = [f"{v}*" for v in current_search.aliases] + ["events-stats-record-view*"]
    try:
        res = current_search_client.snapshot.create(
            repository,
            name,
            body={"indices": ",".join(indices), "include_global_state": False},
            wait_for_completion=wait,
            master_timeout="5m",
        )
        if wait:
            snap = res.get("snapshot", {})
            state = snap.get("state", "UNKNOWN")
            duration = snap.get("duration_in_millis", 0) / 1000
            shards = snap.get("shards", {})
            shards_str = f"{shards.get('successful', 0)}/{shards.get('total', 0)}"
            click.secho(f"Snapshot:  {snap.get('snapshot')}", fg=_STATE_COLORS.get(state))
            click.echo(f"State:     {state}")
            click.echo(f"Duration:  {duration:.1f}s")
            click.echo(f"Shards:    {shards_str}")
        else:
            _print_response(res)
    except Exception as err:
        click.secho(str(err), fg="red")


@snapshot.command("delete")
@with_appcontext
@click.argument("repository")
@click.argument("name")
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to delete a snapshot?",
)
def delete_snapshot(repository, name):
    """Delete a snapshot from a repository."""
    try:
        _print_response(current_search_client.snapshot.delete(repository, name))
    except Exception as err:
        click.secho(str(err), fg="red")


@snapshot.command("restore")
@with_appcontext
@click.argument("repository")
@click.argument("name")
@click.option("-w", "--wait", is_flag=True, default=False, help="Wait for the restore to complete before returning.")
@click.option(
    "-d",
    "--delete",
    "delete_indices",
    is_flag=True,
    default=False,
    help=(
        "Delete RERO ILS indices before restoring instead of closing all cluster indices. "
        "Safer for production: system and Search Dashboards indices are left untouched."
    ),
)
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to restore this snapshot? This will disrupt or delete existing indices.",
)
def restore_snapshot(repository, name, wait, delete_indices):
    """Restore a snapshot into the cluster.

    By default all cluster indices are closed before the restore and reopened
    afterwards (required by SEARCH when restoring to existing indices).

    With --delete, only RERO ILS indices (application aliases +
    events-stats-record-view*) are deleted beforehand. This avoids touching
    system or SEARCH Dashboards indices that are not part of the snapshot.
    """
    try:
        if delete_indices:
            rero_indices = ",".join([f"{v}*" for v in current_search.aliases] + ["events-stats-record-view*"])
            click.secho(f"Indices to delete: {rero_indices}", fg="yellow")
            if not click.confirm("Confirm deletion of the above indices before restore?"):
                raise click.Abort()
            current_search_client.indices.delete(index=rero_indices, allow_no_indices=True, ignore_unavailable=True)
            click.secho("RERO ILS indices deleted.")
        else:
            current_search_client.indices.close(index="*", allow_no_indices=True, ignore_unavailable=True)
            click.secho("All indices are closed.")
        _print_response(
            current_search_client.snapshot.restore(repository, name, master_timeout="5m", wait_for_completion=wait)
        )
        if not delete_indices:
            if wait:
                click.secho("Opening all indices...")
                current_search_client.indices.open(index="*", allow_no_indices=True, ignore_unavailable=True)
                click.secho("All indices are open.")
            else:
                click.secho("Restore running in background. Open indices manually once complete.")
    except click.Abort:
        raise
    except Exception as err:
        click.secho(str(err), fg="red")
