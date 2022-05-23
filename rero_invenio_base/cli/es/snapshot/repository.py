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

"""Click elasticsearch snapshot repository command-line utilities."""


import json

import click
from flask.cli import with_appcontext
from invenio_search import current_search_client

from ...shared import abort_if_false


@click.group()
def repository():
    """Elasticsearch repository commands."""


@repository.command('list')
@with_appcontext
def list_repository():
    """List repository."""
    try:
        click.secho(
            json.dumps(
                current_search_client.snapshot.get_repository(),
                indent=2
            ),
            fg='green'
        )
    except Exception as err:
        click.secho(str(err), fg='red')


@repository.command('create')
@with_appcontext
@click.argument('repository')
@click.argument('location')
@click.option('-c', '--compress', help="compress=True", is_flag=True,
              default=False)
def create_repository(repository, location, compress):
    """Create repository."""
    try:
        snapshot_body = {
            'type': 'fs',
            'settings': {
                'location': f'{location}/{repository}',
                'compress': compress
            }
        }
        click.secho(
            json.dumps(
                current_search_client.snapshot.create_repository(
                    repository, body=snapshot_body),
                indent=2
            ),
            fg='green'
        )
    except Exception as err:
        click.secho(str(err), fg='red')


@repository.command('delete')
@with_appcontext
@click.argument('repository')
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to delete a repository?')
def delete_repository(repository):
    """Delete a repository."""
    try:
        click.secho(
            json.dumps(
                current_search_client.snapshot.delete_repository(repository),
                indent=2
            ),
            fg='red'
        )
    except Exception as err:
        click.secho(str(err), fg='red')
