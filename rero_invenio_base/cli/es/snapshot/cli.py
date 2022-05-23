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

"""Click elasticsearch snapshot command-line utilities."""

import json
from datetime import datetime

import click
from elasticsearch_dsl import Index
from flask.cli import with_appcontext
from invenio_search import current_search, current_search_client

from ...shared import abort_if_false
from .repository import repository


@click.group()
def snapshot():
    """Elasticsearch snapshot commands."""


snapshot.add_command(repository)


@snapshot.command('list')
@with_appcontext
@click.option('-n', '--name', help="default=_all", default='_all')
@click.argument('repository')
def list_snapshot(repository, name):
    """List snapshot."""
    try:
        snapshots = current_search_client.snapshot.get(repository, name)
        infos = snapshots
        if name == '_all':
            infos = [{
                    'snapshot': snapshot['snapshot'],
                    'start_time': snapshot['start_time'],
                    'duration': snapshot['duration_in_millis'] / 1000,
                    'shards': snapshot['shards'],
                    'state': snapshot['state'],
                    'uuid': snapshot['uuid']
                }
                for snapshot in snapshots['snapshots']
            ]
        click.secho(json.dumps(infos, indent=2), fg='green')
    except Exception as err:
        click.secho(str(err), fg='red')


@snapshot.command('create')
@with_appcontext
@click.argument('repository')
@click.option('-n', '--name', help="default={YYYY.MM.DD_HH:MM:SS}",
              default=datetime.utcnow().strftime('%Y.%m.%d_%H:%M:%S'))
@click.option('-w', '--wait', help="wait=True", is_flag=True, default=False)
def create_snapshot(repository, name, wait):
    """Create a new snapshot."""
    indices = [
        f'{v}*' for v in current_search.aliases.keys()
    ] + ['events-stats-record-view*']
    try:
        click.secho(
            json.dumps(
                current_search_client.snapshot.create(
                    repository,
                    name,
                    body=dict(
                        indices=','.join(indices),
                        include_global_state=False
                    ),
                    wait_for_completion=wait,
                    master_timeout='5m'
                ),
                indent=2
            ),
            fg='green'
        )
    except Exception as err:
        click.secho(str(err), fg='red')


@snapshot.command('delete')
@with_appcontext
@click.argument('repository')
@click.argument('name')
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to delete a snapshot?')
def delete_snapshot(repository, name):
    """Delete a snapshot."""
    try:
        click.secho(
            json.dumps(
                current_search_client.snapshot.delete(repository, name),
                indent=2
            ),
            fg='red'
        )
    except Exception as err:
        click.secho(str(err), fg='red')


@snapshot.command('restore')
@with_appcontext
@click.argument('repository')
@click.argument('name')
@click.option('-w', '--wait', help="wait=True", is_flag=True, default=False)
def restore_snapshot(repository, name, wait):
    """Restore a snapshot."""
    try:
        i = Index('_all', using=current_search_client)
        click.secho('Closing all indices...', fg='')
        i.close()
        click.secho('All indices are closed.')
        click.secho(json.dumps(
            current_search_client.snapshot.restore(
                repository,
                name,
                master_timeout='5m',
                wait_for_completion=wait
            ), indent=2), fg='green')
        click.secho('Opening all indices...')
        i.open()
        click.secho('All indices are open.')
    except Exception as err:
        click.secho(str(err), fg='red')
