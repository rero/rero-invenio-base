# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search snapshot command-line utilities."""

import json
import sys
from datetime import UTC, datetime

import click
from flask import current_app
from flask.cli import with_appcontext
from invenio_search import current_search_client

from ...shared import abort_if_false
from .repository import repository

# the client aborts a read after 10s by default, which would give up on a
# snapshot that is still running on the cluster.
WAIT_REQUEST_TIMEOUT = 86400

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


def _instance_indices():
    """Return the index pattern covering every index of this instance.

    Matches on SEARCH_INDEX_PREFIX, so indices no alias knows about, such as
    the invenio-stats ones, are covered too. Without a prefix the instance owns
    the cluster: take everything but the system indices.
    """
    prefix = current_app.config.get("SEARCH_INDEX_PREFIX") or ""
    return f"{prefix}*" if prefix else "*,-.*,-ilm-history-*"


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
        sys.exit(1)


@snapshot.command("create")
@with_appcontext
@click.argument("repository")
@click.option(
    "-n",
    "--name",
    default=lambda: datetime.now(UTC).strftime("%Y.%m.%d_%H:%M:%S"),
    help="Snapshot name. Defaults to the current UTC timestamp (YYYY.MM.DD_HH:MM:SS).",
)
@click.option("-i", "--indices", default=None, help="Index pattern to capture. Defaults to the instance indices.")
@click.option(
    "-g",
    "--global-state/--no-global-state",
    "global_state",
    default=True,
    help="Capture the global state: index templates, pipelines, cluster settings.",
)
@click.option("-w", "--wait", is_flag=True, default=False, help="Wait for the snapshot to complete before returning.")
def create_snapshot(repository, name, indices, global_state, wait):
    """Create a snapshot of all indices of this instance.

    Aborts when the pattern matches nothing, rather than writing an empty snapshot.
    """
    indices = indices or _instance_indices()
    found = sorted(idx["index"] for idx in current_search_client.cat.indices(index=indices, h="index", format="json"))
    if not found:
        click.secho(f"No index matches '{indices}'. Aborting.", fg="red")
        sys.exit(1)
    click.secho(f"Snapshot '{name}': {len(found)} indices matching '{indices}'.", fg="green")
    try:
        res = current_search_client.snapshot.create(
            repository,
            name,
            body={"indices": indices, "include_global_state": global_state},
            wait_for_completion=wait,
            master_timeout="5m",
            request_timeout=WAIT_REQUEST_TIMEOUT if wait else None,
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
            click.secho(f"Snapshot '{name}' started. Follow it with: snapshot list {repository} -n {name}", fg="green")
    except Exception as err:
        click.secho(f"ERROR SNAPSHOT: {err}", fg="red")
        if getattr(err, "error", None) == "invalid_snapshot_name_exception":
            click.secho(f"Delete '{name}' first, or pick another name with --name.", fg="yellow")
        sys.exit(1)


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
        sys.exit(1)


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
        "Delete the instance indices instead of closing all cluster indices. "
        "Safer in production: system and Search Dashboards indices are left untouched."
    ),
)
@click.option(
    "-g",
    "--global-state",
    "global_state",
    is_flag=True,
    default=False,
    help="Also restore the global state. Overwrites index templates, pipelines and cluster settings.",
)
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to restore this snapshot? This will disrupt or delete existing indices.",
)
def restore_snapshot(repository, name, wait, delete_indices, global_state):
    """Restore a snapshot into the cluster.

    By default all cluster indices are closed before the restore and reopened
    afterwards, as SEARCH requires to restore over existing indices. With
    --delete the instance indices are dropped beforehand instead.
    """
    closed = False
    try:
        if delete_indices:
            instance_indices = _instance_indices()
            click.secho(f"Indices to delete: {instance_indices}", fg="yellow")
            if not click.confirm("Confirm deletion of the above indices before restore?"):
                raise click.Abort()
            current_search_client.indices.delete(index=instance_indices, allow_no_indices=True, ignore_unavailable=True)
            click.secho("Instance indices deleted.")
        else:
            current_search_client.indices.close(index="*", allow_no_indices=True, ignore_unavailable=True)
            closed = True
            click.secho("All indices are closed.")
        _print_response(
            current_search_client.snapshot.restore(
                repository,
                name,
                body={"include_global_state": global_state},
                master_timeout="5m",
                wait_for_completion=wait,
                request_timeout=WAIT_REQUEST_TIMEOUT if wait else None,
            )
        )
        if closed:
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
        if closed:
            # nothing is restoring any more, so leaving the cluster closed,
            # system indices included, would only add an outage to the failure.
            click.secho("Restore failed, reopening all indices...", fg="yellow")
            current_search_client.indices.open(index="*", allow_no_indices=True, ignore_unavailable=True)
            click.secho("All indices are open.", fg="yellow")
        sys.exit(1)
