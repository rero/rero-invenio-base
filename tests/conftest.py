# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Pytest configuration.

See https://pytest-invenio.readthedocs.io/ for documentation on which test
fixtures are available.
"""

import copy

import pytest
from click.testing import CliRunner
from flask import Flask
from invenio_db import InvenioDB
from invenio_records_rest import config as _config
from invenio_search import InvenioSearch, current_search_client

from rero_invenio_base import REROInvenioBase
from rero_invenio_base.modules.export.ext import ReroInvenioBaseExportApp


@pytest.fixture(scope="function")
def new_index_name1():
    """Fixtures index name."""
    yield "records-record-v1.0.0"


@pytest.fixture(scope="function")
def new_index_name2():
    """Return another fixture index name."""
    yield "records-2"


@pytest.fixture(scope="function")
def snapshot_repository(app, search, tmp_path):
    """Register a filesystem snapshot repository in a per-test location.

    ``path.repo`` is a static node setting and cannot be created from a test, so
    docker-services.yml points it at a directory inside the container. The
    location registered here is *relative* to it, which keeps the repository
    host-OS independent; ``tmp_path`` only supplies a name unique to this test.

    :returns: name of the registered repository.
    """
    name = "tests"
    current_search_client.snapshot.create_repository(
        name, body={"type": "fs", "settings": {"location": tmp_path.name, "compress": False}}
    )
    yield name
    current_search_client.snapshot.delete_repository(name, ignore=[404])


@pytest.fixture(scope="function")
def es_runner(app, search, new_index_name1, new_index_name2):
    """Create and remove indexes into search."""
    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )
    search = app.extensions["invenio-search"]
    if "records" not in search.aliases:
        search.register_mappings("records", "mock_modules.mappings")
    yield CliRunner()
    for i in [new_index_name1, new_index_name2]:
        current_search_client.indices.delete(
            index=i,
            ignore=[400, 404],
        )


@pytest.fixture(scope="module")
def celery_config():
    """Override pytest-invenio fixture.

    TODO: Remove this fixture if you add Celery support.
    """
    return {}


@pytest.fixture(scope="module")
def create_app(instance_path):
    """Application factory fixture."""

    def factory(**config):
        app = Flask("testapp", instance_path=instance_path)
        app.config.update(**config)
        app.config.update(RECORDS_REST_ENDPOINTS=copy.deepcopy(_config.RECORDS_REST_ENDPOINTS))
        REROInvenioBase(app)
        ReroInvenioBaseExportApp(app)
        InvenioDB(app)
        InvenioSearch(app)
        return app

    return factory


@pytest.fixture
def rebuild_runner(app, search):
    """Runner for rebuild_index tests; cleans up all records-* indices."""
    current_search_client.indices.delete(index="records-*", ignore_unavailable=True)
    search = app.extensions["invenio-search"]
    if "records" not in search.aliases:
        search.register_mappings("records", "mock_modules.mappings")
    yield CliRunner()
    current_search_client.indices.delete(index="records-*", ignore_unavailable=True)
