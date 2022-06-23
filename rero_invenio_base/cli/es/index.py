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
from elasticsearch_dsl import Index
from invenio_search import current_search, current_search_client
from invenio_search.cli import es_version_check, with_appcontext
from jsonpatch import make_patch


@click.group()
def index():
    """Elasticsearch index commands."""


@index.command('reindex')
@with_appcontext
@es_version_check
@click.argument('source')
@click.argument('destination')
def reindex(source, destination):
    """Reindex from source.

    See: https://www.elastic.co/guide/en/elasticsearch/reference/7.10/docs-reindex.html # noqa
    """
    res = current_search_client.reindex(
        body=dict(
            source=dict(
                index=source
            ),
            dest=dict(
                index=destination,
                version_type='external_gte'
            )
        ),
        wait_for_completion=False
    )
    click.secho(f'Task: {res["task"]}', fg='green')


@index.command('open')
@with_appcontext
@click.option('-i', '--index', help="default=_all", default='_all')
def open_index(index):
    """Open elasticsearch index."""
    try:
        i = Index(index, using=current_search_client)
        click.secho(json.dumps(i.open(), indent=2), fg='green')
    except Exception as err:
        click.secho(str(err), fg='red')


@index.command('close')
@with_appcontext
@click.option('-i', '--index', help="default=_all", default='_all')
def close_index(index):
    """Close elasticsearch index."""
    try:
        i = Index(index, using=current_search_client)
        click.secho(json.dumps(i.close(), indent=2), fg='green')
    except Exception as err:
        click.secho(str(err), fg='red')


@index.command('switch')
@with_appcontext
@es_version_check
@click.argument('old')
@click.argument('new')
def switch_index(old, new):
    """Switch index using the elasticsearch aliases.

    :param old: full name of the old index
    :param new: full name of the fresh created index
    """
    aliases = current_search_client.indices.get_alias().get(old)\
        .get('aliases').keys()
    for alias in aliases:
        current_search_client.indices.put_alias(new, alias)
        current_search_client.indices.delete_alias(old, alias)
    click.secho('Sucessfully switched.', fg='green')


@index.command('create')
@with_appcontext
@es_version_check
@click.option(
    '-t', '--templates/--no-templates', 'templates', is_flag=True,
    default=True)
@click.option(
    '-v', '--verbose/--no-verbose', 'verbose', is_flag=True, default=False)
@click.argument('resource')
@click.argument('index')
def create_index(resource, index, verbose, templates):
    """Create a new index based on the mapping of a given resource.

    :param resource: the resource such as documents.
    :param index: the index name such as documents-document-v0.0.1-20211014
    :param verbose: display addtional message.
    :param templates: update also the es templates.
    """
    if templates:
        tbody = current_search_client.indices.get_template()
        for tmpl in current_search.put_templates():
            click.secho(f'file:{tmpl[0]}, ok: {tmpl[1]}', fg='green')
            new_tbody = current_search_client.indices.get_template()
            if patch := make_patch(new_tbody, tbody):
                click.secho('Templates are updated.', fg='green')
                if verbose:
                    click.secho('Diff in templates', fg='green')
                    click.echo(patch)
            else:
                click.secho('Templates did not changed.', fg='yellow')

    f_mapping = list(current_search.aliases.get(resource).values()).pop()
    mapping = json.load(open(f'{f_mapping}'))
    current_search_client.indices.create(index, mapping)
    click.secho(f'Index {index} has been created.', fg='green')


@index.command()
@click.option('--aliases', '-a', multiple=True, help='all if not specified')
@click.option(
    '-s', '--settings/--no-settings', 'settings', is_flag=True, default=False)
@with_appcontext
def update_mapping(aliases, settings):
    """Update the mapping of a given alias."""
    if not aliases:
        aliases = current_search.aliases.keys()
    for alias in aliases:
        for index, f_mapping in iter(
            current_search.aliases.get(alias).items()
        ):
            mapping = json.load(open(f_mapping))
            try:
                if mapping.get('settings') and settings:
                    current_search_client.indices.close(index=index)
                    current_search_client.indices.put_settings(
                        body=mapping.get('settings'), index=index)
                    current_search_client.indices.open(index=index)
                res = current_search_client.indices.put_mapping(
                    body=mapping.get('mappings'), index=index)
            except Exception as excep:
                click.secho(
                    f'error: {excep}', fg='red')
            if res.get('acknowledged'):
                click.secho(
                    f'index: {index} has been sucessfully updated',
                    fg='green')
            else:
                click.secho(
                    f'error: {res}', fg='red')
