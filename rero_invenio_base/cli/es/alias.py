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

import click
from flask.cli import with_appcontext
from invenio_search import current_search_client

from ..shared import abort_if_false


@click.group()
def alias():
    """Elasticsearch alias commands."""


@alias.command('get')
@with_appcontext
def get_alias():
    """Get elasticsearch aliases."""
    click.secho(
        json.dumps(current_search_client.indices.get_alias(), indent=2),
        fg='green'
    )


@alias.command('put')
@with_appcontext
@click.argument('index')
@click.argument('name')
def put_alias(index, name):
    """Put elasticsearch alias."""
    try:
        click.secho(
            json.dumps(
                current_search_client.indices.put_alias(index, name),
                indent=2
            ),
            fg='green'
        )
    except Exception as err:
        click.secho(str(err), fg='red')


@alias.command('delete')
@with_appcontext
@click.argument('index')
@click.argument('name')
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to delete an alias?')
def delete_alias(index, name):
    """Delete elasticsearch alias."""
    try:
        click.secho(
            json.dumps(
                current_search_client.indices.delete_alias(index, name),
                indent=2
            ),
            fg='green'
        )
    except Exception as err:
        click.secho(str(err), fg='red')
