# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click elasticsearch index command-line utilities."""

import json

import click
from flask.cli import with_appcontext
from invenio_search import current_search_client

from ..shared import abort_if_false


@click.group()
def alias():
    """Elasticsearch alias commands."""


@alias.command("get")
@with_appcontext
def get_alias():
    """Get elasticsearch aliases."""
    click.secho(json.dumps(current_search_client.indices.get_alias(), indent=2), fg="green")


@alias.command("put")
@with_appcontext
@click.argument("index")
@click.argument("name")
def put_alias(index, name):
    """Put elasticsearch alias."""
    try:
        click.secho(
            json.dumps(current_search_client.indices.put_alias(index, name), indent=2),
            fg="green",
        )
    except Exception as err:
        click.secho(str(err), fg="red")


@alias.command("delete")
@with_appcontext
@click.argument("index")
@click.argument("name")
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to delete an alias?",
)
def delete_alias(index, name):
    """Delete elasticsearch alias."""
    try:
        click.secho(
            json.dumps(current_search_client.indices.delete_alias(index, name), indent=2),
            fg="green",
        )
    except Exception as err:
        click.secho(str(err), fg="red")
