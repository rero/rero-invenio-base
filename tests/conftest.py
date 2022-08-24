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

"""Pytest configuration.

See https://pytest-invenio.readthedocs.io/ for documentation on which test
fixtures are available.
"""


import contextlib
import copy

import pytest
from click.testing import CliRunner
from flask import Flask
from invenio_db import InvenioDB
from invenio_records_rest import config as _config
from invenio_search import InvenioSearch, current_search_client

from rero_invenio_base import REROInvenioBase
from rero_invenio_base.modules.export.ext import ReroInvenioBaseExportApp


@pytest.fixture(scope='function')
def new_index_name1():
    """Fixtures index name."""
    yield 'records-record-v1.0.0'


@pytest.fixture(scope='function')
def new_index_name2():
    """An other fixture index name."""
    yield 'records-2'


@pytest.fixture(scope='function')
def es_runner(app, es, new_index_name1, new_index_name2):
    """A cli runner that create and remove indexes into es."""
    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )
    search = app.extensions['invenio-search']
    with contextlib.suppress(AssertionError):
        search.register_mappings('records', 'mock_modules.mappings')
    yield CliRunner()
    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )


@pytest.fixture(scope='module')
def celery_config():
    """Override pytest-invenio fixture.

    TODO: Remove this fixture if you add Celery support.
    """
    return {}


@pytest.fixture(scope='module')
def create_app(instance_path):
    """Application factory fixture."""
    def factory(**config):
        app = Flask('testapp', instance_path=instance_path)
        app.config.update(**config)
        app.config.update(
            RECORDS_REST_ENDPOINTS=copy.deepcopy(
                _config.RECORDS_REST_ENDPOINTS)
        )
        REROInvenioBase(app)
        ReroInvenioBaseExportApp(app)
        InvenioDB(app)
        InvenioSearch(app)
        return app
    return factory
