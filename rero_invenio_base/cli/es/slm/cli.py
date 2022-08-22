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
import sys

import click
from elasticsearch import TransportError
from flask.cli import with_appcontext
from invenio_search import current_search_client

from ...shared import abort_if_false


@click.group()
def slm():
    """Elasticsearch snapshot lifecycle management commands."""


@slm.command()
@with_appcontext
def stats():
    """Lifecycle stats."""
    try:
        click.secho(
            json.dumps(current_search_client.slm.get_stats(), indent=2),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        sys.exit(1)
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)


@slm.command()
@with_appcontext
def status():
    """Lifecycle status."""
    try:
        click.secho(
            json.dumps(current_search_client.slm.get_status(), indent=2),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        sys.exit(1)
    except Exception as err:
        click.secho(str(err), fg='red')
        sys.exit(1)


@slm.command()
@with_appcontext
def start():
    """Start lifecycle."""
    try:
        click.secho(
            json.dumps(current_search_client.slm.start(), indent=2),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort


@slm.command()
@with_appcontext
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to stop the lifecycle?')
def stop():
    """Stop lifecycle."""
    try:
        click.secho(
            json.dumps(current_search_client.slm.stop(), indent=2),
            fg='red'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort


@slm.command()
@with_appcontext
@click.argument('policy_id')
@click.option('--yes-i-know', is_flag=True, callback=abort_if_false,
              expose_value=False,
              prompt='Do you really want to delete a lifecycle?')
def delete(policy_id):
    """Delete lifecycle."""
    try:
        click.secho(
            json.dumps(
                current_search_client.slm.delete_lifecycle(policy_id),
                indent=2
            ),
            fg='red'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort


@slm.command()
@with_appcontext
@click.argument('policy_id')
def execute(policy_id):
    """Execute lifecycle."""
    try:
        click.secho(
            json.dumps(
                current_search_client.slm.execute_lifecycle(policy_id),
                indent=2
            ),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort


@slm.command()
@with_appcontext
@click.option('-n', '--name', help="default=all", default=None)
def get(name):
    """Get lifecycle."""
    try:
        click.secho(
            json.dumps(
                current_search_client.slm.get_lifecycle(name),
                indent=2
            ),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort


@slm.command()
@with_appcontext
@click.argument('policy_id')
@click.argument('body_file', type=click.File('r'))
def put(policy_id, body_file):
    """Put lifecycle."""
    try:
        body = json.load(body_file)
        click.secho(
            json.dumps(
                current_search_client.slm.put_lifecycle(policy_id, body),
                indent=2
            ),
            fg='green'
        )
    except TransportError as err:
        click.secho(f'SLM NOT ENABLED: {err}', fg='red')
        click.Abort
    except Exception as err:
        click.secho(str(err), fg='red')
        click.Abort
