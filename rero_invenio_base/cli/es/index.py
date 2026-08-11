# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search index command-line utilities."""

import json
import sys
from datetime import UTC, datetime
from pprint import pformat

import click
from elasticsearch import NotFoundError, RequestError, TransportError
from invenio_search import current_search, current_search_client

try:
    from invenio_search.cli import es_version_check
except ImportError:
    from invenio_search.cli import search_version_check as es_version_check

from invenio_search.cli import with_appcontext
from jsonpatch import make_patch


def _create_index_from_mapping(index_name, f_mapping):
    """Create an Search index from a mapping file."""
    with open(f_mapping) as mapping_file:
        mapping = json.load(mapping_file)
    current_search_client.indices.create(index=index_name, body=mapping)


def _log_task_progress(task, count):
    """Fetch current task status and print a one-line progress update.

    :param task: task id.
    :param count: elapsed seconds to display.
    """
    try:
        res = current_search_client.tasks.get(task)
        status = res.get("task", {}).get("status", {})
        created = status.get("created", "?")
        total = status.get("total", "?")
        click.secho(f"Watching task: {task} {count} seconds ... {created}/{total}", fg="green")
    except TransportError:
        click.secho(f"Watching task: {task} {count} seconds ...", fg="green")


def _watch_reindex_task(task, interval, verbose):
    """Watch a reindex task until completion using server-side long-polling.

    :param task: task id returned by the reindex API.
    :param interval: seconds to wait per poll (passed as timeout to the tasks API).
    :param verbose: print task progress on each poll.
    :returns: True on success, False if the task reported failures.
    """
    count = 0
    while True:
        try:
            res = current_search_client.tasks.get(task, wait_for_completion=True, timeout=f"{interval}s")
        except NotFoundError:
            if verbose:
                click.secho(f"Finished task: {task} {count} seconds.", fg="yellow")
            return True
        except RequestError as err:
            if err.error != "index_closed_exception":
                raise
            if verbose:
                click.secho(f"Finished task: {task} {count} seconds.", fg="yellow")
            return True
        except TransportError as err:
            if err.error != "timeout_exception":
                raise
            count += interval
            if verbose:
                _log_task_progress(task, count)
            continue
        if res.get("completed"):
            break
        count += interval
        if verbose:
            _log_task_progress(task, count)
    if verbose:
        click.secho(f"Finished task: {task} {count} seconds.", fg="yellow")
        click.secho(f"{pformat(res.get('response'))}", fg="yellow")
    if failures := res.get("response", {}).get("failures"):
        click.secho(f"ERROR REINDEX: {failures}", fg="red")
        return False
    return True


def _do_reindex(src, dest, interval, verbose, label="Task"):
    """Submit a reindex task and optionally wait for it.

    :param src: source index name.
    :param dest: destination index name.
    :param interval: seconds between polls (0 = fire and forget).
    :param verbose: print task progress on each poll.
    :param label: prefix shown before the task id.
    :returns: True on success or when fire-and-forget, False on task failures.
    """
    res = current_search_client.reindex(
        body={
            "source": {"index": src},
            "dest": {"index": dest, "version_type": "external_gte"},
        },
        wait_for_completion=False,
    )
    task = res["task"]
    click.secho(f"{label}: {task}", fg="green")
    if interval > 0:
        return _watch_reindex_task(task, interval, verbose)
    return True


def _switch_aliases(from_index, to_index):
    """Move all aliases from one index to another.

    :param from_index: index that currently holds the aliases.
    :param to_index: index that should receive the aliases.
    :returns: list of alias names that were moved.
    """
    aliases = list(current_search_client.indices.get_alias().get(from_index, {}).get("aliases", {}).keys())
    for alias in aliases:
        current_search_client.indices.put_alias(to_index, alias)
        current_search_client.indices.delete_alias(from_index, alias)
        click.secho(f"Alias '{alias}' → {to_index}.", fg="green")
    return aliases


def _update_templates(verbose, templates):
    """Update Search templates if requested."""
    if not templates:
        return
    tbody = current_search_client.indices.get_template()
    for tmpl in current_search.put_templates():
        click.secho(f"file:{tmpl[0]}, ok: {tmpl[1]}", fg="green")
        new_tbody = current_search_client.indices.get_template()
        if patch := make_patch(tbody, new_tbody):
            click.secho("Templates are updated.", fg="green")
            if verbose:
                click.secho("Diff in templates", fg="green")
                click.echo(patch)
        else:
            click.secho("Templates did not change.", fg="yellow")


@click.group()
def index():
    """Search index commands."""


@index.command("reindex")
@with_appcontext
@es_version_check
@click.argument("source")
@click.argument("destination")
def reindex(source, destination):
    """Reindex from source.

    See: https://www.elastic.co/guide/en/elasticsearch/reference/7.10/docs-reindex.html
    """
    res = current_search_client.reindex(
        body={
            "source": {"index": source},
            "dest": {"index": destination, "version_type": "external_gte"},
        },
        wait_for_completion=False,
    )
    click.secho(f"Task: {res['task']}", fg="green")


@index.command("open")
@with_appcontext
@click.option("-i", "--index", help="default=_all", default="*")
def open_index(index):
    """Open Search index."""
    try:
        click.secho(
            json.dumps(
                current_search_client.indices.open(index=index, allow_no_indices=True, ignore_unavailable=True),
                indent=2,
            ),
            fg="green",
        )
    except Exception as err:
        click.secho(str(err), fg="red")


@index.command("close")
@with_appcontext
@click.option("-i", "--index", help="default=_all", default="*")
def close_index(index):
    """Close Search index."""
    try:
        click.secho(
            json.dumps(
                current_search_client.indices.close(index=index, allow_no_indices=True, ignore_unavailable=True),
                indent=2,
            ),
            fg="green",
        )
    except Exception as err:
        click.secho(str(err), fg="red")


@index.command("switch")
@with_appcontext
@es_version_check
@click.argument("old")
@click.argument("new")
def switch_index(old, new):
    """Switch index using the Search aliases.

    :param old: full name of the old index
    :param new: full name of the fresh created index
    """
    try:
        _switch_aliases(old, new)
        click.secho("Successfully switched.", fg="green")
    except Exception as err:
        click.secho(f"ERROR SWITCH: {err}", fg="red")
        sys.exit(1)


@index.command("create")
@with_appcontext
@es_version_check
@click.option("-t", "--templates/--no-templates", "templates", is_flag=True, default=True)
@click.option("-v", "--verbose/--no-verbose", "verbose", is_flag=True, default=False)
@click.argument("resource")
@click.argument("index")
def create_index(resource, index, verbose, templates):
    """Create a new index based on the mapping of a given resource.

    :param resource: the resource such as documents.
    :param index: the index name such as documents-document-v0.0.1-20211014
    :param verbose: display additional message.
    :param templates: update also the es templates.
    """
    _update_templates(verbose, templates)

    f_mapping = list(current_search.aliases.get(resource).values()).pop()
    with open(f_mapping) as mapping:
        current_search_client.indices.create(index, json.load(mapping))
    click.secho(f"Index {index} has been created.", fg="green")


@index.command()
@click.option("--aliases", "-a", multiple=True, help="all if not specified")
@click.option("-s", "--settings/--no-settings", "settings", is_flag=True, default=False)
@with_appcontext
def update_mapping(aliases, settings):
    """Update the mapping of a given alias."""
    if not aliases:
        aliases = current_search.aliases.keys()
    for alias in aliases:
        for index, f_mapping in iter(current_search.aliases.get(alias).items()):
            with open(f_mapping) as mapping_file:
                mapping = json.load(mapping_file)
                try:
                    if mapping.get("settings") and settings:
                        current_search_client.indices.close(index=index)
                        current_search_client.indices.put_settings(body=mapping.get("settings"), index=index)
                        current_search_client.indices.open(index=index)
                    if res := current_search_client.indices.put_mapping(body=mapping.get("mappings"), index=index):
                        if res.get("acknowledged"):
                            click.secho(f"index: {index} has been successfully updated", fg="green")
                        else:
                            click.secho(f"error: {index}: {res}", fg="red")
                except TransportError as err:
                    click.secho(f"error: {index}: {err}", fg="red")


@index.command("move")
@with_appcontext
@es_version_check
@click.argument("resource")
@click.argument("old")
@click.argument("new")
@click.option("-t", "--templates/--no-templates", "templates", is_flag=True, default=True)
@click.option("-v", "--verbose/--no-verbose", "verbose", is_flag=True, default=False)
@click.option("-n", "--interval", default=1, type=int, help="seconds to wait between updates")
def move_index(resource, old, new, templates, verbose, interval):
    """Move index using the Search resource.

    :param resource: the resource such as documents.
    :param old: full name of the old index
    :param new: full name of the fresh created index
    :param verbose: display additional message.
    :param templates: update also the es templates.
    """
    try:
        _update_templates(verbose, templates)
        f_mapping = list(current_search.aliases.get(resource).values()).pop()
        _create_index_from_mapping(new, f_mapping)
        click.secho(f"Index {new} has been created.", fg="green")
    except Exception as err:
        click.secho(f"ERROR CREATE: {err}", fg="red")
        sys.exit(1)

    if not _do_reindex(old, new, interval, verbose):
        sys.exit(2)

    try:
        _switch_aliases(old, new)
        click.secho("Successfully switched.", fg="green")
    except Exception as err:
        click.secho(f"ERROR SWITCH: {err}", fg="red")
        sys.exit(3)


def _reindex_pass(src, dest, interval, verbose, label, src_label, dest_label, confirm_msg, abort_msg, exit_base):
    """Reindex src→dest, display counts, ask for confirmation, switch aliases, delete src.

    :param src: source index.
    :param dest: destination index.
    :param interval: seconds between reindex task polls (0 = fire and forget).
    :param verbose: show reindex task progress.
    :param label: prefix shown before the reindex task id.
    :param src_label: short description of src shown in the count line.
    :param dest_label: short description of dest shown in the count line.
    :param confirm_msg: text passed to click.confirm.
    :param abort_msg: message printed when the user declines.
    :param exit_base: base exit code; switch failure = exit_base+1, delete failure = exit_base+2.
    :returns: True if completed, False if the user aborted.
    """
    if not _do_reindex(src, dest, interval, verbose, label=label):
        sys.exit(exit_base)

    current_search_client.indices.refresh(index=dest)
    src_count = current_search_client.count(index=src).get("count", "?")
    dest_count = current_search_client.count(index=dest).get("count", "?")
    click.secho(f"  {src}: {src_count} docs  ({src_label})", fg="yellow")
    click.secho(f"  {dest}: {dest_count} docs  ({dest_label})", fg="green")

    if not click.confirm(confirm_msg):
        click.secho(abort_msg, fg="yellow")
        return False

    try:
        _switch_aliases(src, dest)
    except Exception as err:
        click.secho(f"ERROR SWITCH: {err}", fg="red")
        sys.exit(exit_base + 1)

    try:
        current_search_client.indices.delete(index=src)
        click.secho(f"Index {src} deleted.", fg="green")
    except Exception as err:
        click.secho(f"ERROR DELETE: {err}", fg="red")
        sys.exit(exit_base + 2)

    return True


def _create_fresh(resource, new_index, f_mapping):
    """Bootstrap a resource that has no index yet: create it and register the alias.

    :param resource: alias name to register.
    :param new_index: index name to create.
    :param f_mapping: path to the mapping file.
    """
    if current_search_client.indices.exists(index=new_index):
        click.secho(f"Index {new_index} already exists but alias '{resource}' is not set. Aborting.", fg="red")
        sys.exit(1)
    click.secho(f"No existing index for '{resource}'. Creating {new_index}...", fg="yellow")
    try:
        _create_index_from_mapping(new_index, f_mapping)
        current_search_client.indices.put_alias(index=new_index, name=resource)
        click.secho(f"Index {new_index} created, alias '{resource}' registered.", fg="green")
    except Exception as err:
        click.secho(f"ERROR CREATE: {err}", fg="red")
        sys.exit(1)


def _create_and_log(index_name, f_mapping, exit_code):
    """Create an index from mapping, log the result, and exit on failure.

    :param index_name: name of the index to create.
    :param f_mapping: path to the mapping file.
    :param exit_code: exit code used when the creation fails.
    """
    try:
        _create_index_from_mapping(index_name, f_mapping)
        click.secho(f"Index {index_name} created.", fg="green")
    except Exception as err:
        click.secho(f"ERROR CREATE: {err}", fg="red")
        sys.exit(exit_code)


@index.command("rebuild")
@with_appcontext
@es_version_check
@click.argument("resource")
@click.option("-t", "--templates/--no-templates", "templates", is_flag=True, default=True)
@click.option("-v", "--verbose/--no-verbose", "verbose", is_flag=True, default=False)
@click.option("-i", "--interval", default=1, type=int, help="seconds to wait between task updates")
@click.option(
    "-n", "--name", default=None, help="Override the destination index name (default: registered name + today's date)."
)
@click.option(
    "-p",
    "--inplace",
    is_flag=True,
    default=False,
    help="Rebuild keeping the same index name (double-move via temp index).",
)
def rebuild_index(resource, templates, verbose, interval, name, inplace):
    """Reindex a resource into an up-to-date index without data loss.

    Normal mode (default): migrate directly ``old → new_index`` where
    ``new_index`` is the registered name suffixed with today's date.

    Inplace mode (``--inplace``): rebuild under the same index name.  A temporary
    index is used so the alias always points to a live index: ``old → tmp`` first,
    then ``tmp → old`` after the original index is recreated fresh.

    :param resource: alias name, e.g. 'patrons'.
    :param templates: update Search templates before rebuilding.
    :param verbose: show template diffs and reindex task progress.
    :param interval: seconds between reindex task updates (0 = fire and forget).
    :param name: explicit destination index name; defaults to registered name + today's date.
    :param inplace: evacuate the current index to a temp before migrating to new_index.
    """
    alias_map = current_search.aliases.get(resource)
    if not alias_map:
        click.secho(f"Unknown resource: '{resource}'.", fg="red")
        click.secho(f"Available: {', '.join(sorted(current_search.aliases))}", fg="yellow")
        sys.exit(1)

    registered_index, f_mapping = next(iter(alias_map.items()))
    new_index = name or f"{registered_index}-{datetime.now(UTC).strftime('%Y%m%d')}"

    try:
        old_indices = list(current_search_client.indices.get_alias(name=resource).keys())
    except NotFoundError:
        old_indices = []

    try:
        _update_templates(verbose, templates)
    except Exception as err:
        click.secho(f"ERROR TEMPLATES: {err}", fg="red")
        sys.exit(1)

    if not old_indices:
        _create_fresh(resource, new_index, f_mapping)
        return

    old_index = old_indices[0]

    if inplace:
        tmp_index = f"{old_index}-tmp-{datetime.now(UTC).strftime('%Y%m%d%H%M%S')}"
        click.secho(f"Rebuilding '{resource}' in place: {old_index} → {tmp_index} → {old_index}", fg="green")
        _create_and_log(tmp_index, f_mapping, exit_code=1)
        if not _reindex_pass(
            src=old_index,
            dest=tmp_index,
            interval=interval,
            verbose=verbose,
            label="Task (pass 1)",
            src_label="current",
            dest_label="temp",
            confirm_msg=f"Move '{old_index}' to temp before rebuilding?",
            abort_msg=f"Aborted. Temp index {tmp_index} exists — delete it manually when done.",
            exit_base=2,
        ):
            return
        src = tmp_index
        final_dest = old_index
        exit_base = 5
    else:
        if old_index == new_index:
            click.secho(f"'{resource}' already points to {new_index}. Nothing to do.", fg="green")
            return
        if current_search_client.indices.exists(index=new_index):
            click.secho(f"Index {new_index} already exists. Aborting.", fg="red")
            sys.exit(1)
        click.secho(f"Rebuilding '{resource}': {old_index} → {new_index}", fg="green")
        src = old_index
        final_dest = new_index
        exit_base = 2

    _create_and_log(final_dest, f_mapping, exit_code=exit_base - 1)
    _reindex_pass(
        src=src,
        dest=final_dest,
        interval=interval,
        verbose=verbose,
        label="Task (pass 2)" if inplace else "Task",
        src_label="temp" if inplace else "old",
        dest_label="rebuilt" if inplace else "new",
        confirm_msg="Switch alias back and delete temp index?" if inplace else "Switch alias and delete source index?",
        abort_msg=f"Aborted. {final_dest} was created but alias still points to {src}.",
        exit_base=exit_base,
    )


@index.command()
@click.option("-i", "--index", default="", help="all if not specified")
@click.option("-a", "--aliases", is_flag=True, default=False, help="Display aliases.")
@click.option("-m", "--mappings", is_flag=True, default=False, help="Display mappings.")
@click.option("-s", "--settings", is_flag=True, default=False, help="Display settings.")
@with_appcontext
def info(index, aliases, mappings, settings):
    """List indices of given alias."""

    def print_info(name, data):
        """Display additional info."""
        msg = pformat(data.get(name))
        click.secho(f"{name}:", fg="yellow")
        click.secho(f"{msg}", fg="yellow")

    indices = current_search_client.indices.get(f"{index}*")
    for index_name, data in indices.items():
        click.secho(f"{index_name}", fg="green")
        if aliases:
            print_info("aliases", data)
        if mappings:
            print_info("mappings", data)
        if settings:
            print_info("settings", data)
