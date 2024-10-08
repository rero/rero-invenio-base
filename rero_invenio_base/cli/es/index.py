# -*- coding: utf-8 -*-
#
# RERO Invenio Base
# Copyright (C) 2022 RERO.
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

"""Click elasticsearch index command-line utilities."""
import json
import sys
from pprint import pformat
from time import sleep

import click
from elasticsearch_dsl import Index
from invenio_search import current_search, current_search_client

try:
    from invenio_search.cli import es_version_check
except ImportError:
    from invenio_search.cli import search_version_check as es_version_check

from invenio_search.cli import with_appcontext
from jsonpatch import make_patch


@click.group()
def index():
    """Elasticsearch index commands."""


@index.command("reindex")
@with_appcontext
@es_version_check
@click.argument("source")
@click.argument("destination")
def reindex(source, destination):
    """Reindex from source.

    See: https://www.elastic.co/guide/en/elasticsearch/reference/7.10/docs-reindex.html # noqa
    """
    res = current_search_client.reindex(
        body=dict(
            source=dict(index=source),
            dest=dict(index=destination, version_type="external_gte"),
        ),
        wait_for_completion=False,
    )
    click.secho(f'Task: {res["task"]}', fg="green")


@index.command("open")
@with_appcontext
@click.option("-i", "--index", help="default=_all", default="_all")
def open_index(index):
    """Open elasticsearch index."""
    try:
        i = Index(index, using=current_search_client)
        click.secho(json.dumps(i.open(), indent=2), fg="green")
    except Exception as err:
        click.secho(str(err), fg="red")


@index.command("close")
@with_appcontext
@click.option("-i", "--index", help="default=_all", default="_all")
def close_index(index):
    """Close elasticsearch index."""
    try:
        i = Index(index, using=current_search_client)
        click.secho(json.dumps(i.close(), indent=2), fg="green")
    except Exception as err:
        click.secho(str(err), fg="red")


@index.command("switch")
@with_appcontext
@es_version_check
@click.argument("old")
@click.argument("new")
def switch_index(old, new):
    """Switch index using the elasticsearch aliases.

    :param old: full name of the old index
    :param new: full name of the fresh created index
    """
    aliases = current_search_client.indices.get_alias().get(old).get("aliases").keys()
    for alias in aliases:
        current_search_client.indices.put_alias(new, alias)
        current_search_client.indices.delete_alias(old, alias)
    click.secho("Successfully switched.", fg="green")


@index.command("create")
@with_appcontext
@es_version_check
@click.option(
    "-t", "--templates/--no-templates", "templates", is_flag=True, default=True
)
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
    if templates:
        tbody = current_search_client.indices.get_template()
        for tmpl in current_search.put_templates():
            click.secho(f"file:{tmpl[0]}, ok: {tmpl[1]}", fg="green")
            new_tbody = current_search_client.indices.get_template()
            if patch := make_patch(new_tbody, tbody):
                click.secho("Templates are updated.", fg="green")
                if verbose:
                    click.secho("Diff in templates", fg="green")
                    click.echo(patch)
            else:
                click.secho("Templates did not changed.", fg="yellow")

    f_mapping = list(current_search.aliases.get(resource).values()).pop()
    mapping = json.load(open(f"{f_mapping}"))
    current_search_client.indices.create(index, mapping)
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
            mapping = json.load(open(f_mapping))
            try:
                if mapping.get("settings") and settings:
                    current_search_client.indices.close(index=index)
                    current_search_client.indices.put_settings(
                        body=mapping.get("settings"), index=index
                    )
                    current_search_client.indices.open(index=index)
                res = current_search_client.indices.put_mapping(
                    body=mapping.get("mappings"), index=index
                )
            except Exception as excep:
                click.secho(f"error: {excep}", fg="red")
            if res.get("acknowledged"):
                click.secho(f"index: {index} has been successfully updated", fg="green")
            else:
                click.secho(f"error: {res}", fg="red")


@index.command("move")
@with_appcontext
@es_version_check
@click.argument("resource")
@click.argument("old")
@click.argument("new")
@click.option(
    "-t", "--templates/--no-templates", "templates", is_flag=True, default=True
)
@click.option("-v", "--verbose/--no-verbose", "verbose", is_flag=True, default=False)
@click.option(
    "-n", "--interval", default=1, type=int, help="seconds to wait between updates"
)
def move_index(resource, old, new, templates, verbose, interval):
    """Move index using the elasticsearch resource.

    :param resource: the resource such as documents.
    :param old: full name of the old index
    :param new: full name of the fresh created index
    :param verbose: display additional message.
    :param templates: update also the es templates.
    """
    # create_index(resource, index, verbose, templates)
    try:
        if templates:
            tbody = current_search_client.indices.get_template()
            for tmpl in current_search.put_templates():
                click.secho(f"file:{tmpl[0]}, ok: {tmpl[1]}", fg="green")
                new_tbody = current_search_client.indices.get_template()
                if patch := make_patch(new_tbody, tbody):
                    click.secho("Templates are updated.", fg="green")
                    if verbose:
                        click.secho("Diff in templates", fg="green")
                        click.echo(patch)
                else:
                    click.secho("Templates did not changed.", fg="yellow")

        f_mapping = list(current_search.aliases.get(resource).values()).pop()
        mapping = json.load(open(f"{f_mapping}"))
        current_search_client.indices.create(new, mapping)
        click.secho(f"Index {new} has been created.", fg="green")
    except Exception as err:
        click.secho(f"ERROR CREATE: {err}", fg="red")
        sys.exit(1)

    res = current_search_client.reindex(
        body=dict(
            source=dict(index=old), dest=dict(index=new, version_type="external_gte")
        ),
        wait_for_completion=False,
    )
    task = res["task"]
    click.secho(f"Task: {task}", fg="green")
    if interval == 0:
        return
    count = 0
    # wait for task
    res = current_search_client.tasks.get(task)
    while not res.get("completed"):
        task_info = res.get("task")
        if verbose and task_info:
            click.secho(f"Watching task: {task} {count} seconds ...", fg="green")
            click.secho(f'{task_info.get("description")}', fg="green")
            click.secho(f'{pformat( task_info.get("status"))}', fg="green")
        sleep(interval)
        count += interval
        res = current_search_client.tasks.get(task)
    if verbose:
        click.secho(f"Finished task: {task} {count} seconds ...", fg="yellow")
        click.secho(f'{pformat(res.get("response"))}', fg="yellow")
    if failures := res.get("failures"):
        click.secho(f"ERROR REINDEX: {failures}", fg="red")
        sys.exit(2)

    # switch index
    try:
        aliases = (
            current_search_client.indices.get_alias().get(old).get("aliases").keys()
        )
        for alias in aliases:
            current_search_client.indices.put_alias(new, alias)
            current_search_client.indices.delete_alias(old, alias)
        click.secho("Successfully switched.", fg="green")
    except Exception as err:
        click.secho(f"ERROR SWITCH: {err}", fg="red")
        sys.exit(3)


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
    for index, data in indices.items():
        click.secho(f"{index}", fg="green")
        if aliases:
            print_info("aliases", data)
        if mappings:
            print_info("mappings", data)
        if settings:
            print_info("settings", data)
