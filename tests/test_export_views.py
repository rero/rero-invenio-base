# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the streamed export views against the search cluster."""

import pytest
from flask import Response
from invenio_search import RecordsSearch, current_search_client

from rero_invenio_base.modules.export.views import create_blueprint_from_app

RECORD_COUNT = 15  # more than the 10 hits of a default search page


class RecordSearch(RecordsSearch):
    """Search the test records only."""

    class Meta(RecordsSearch.Meta):
        """Target the ``records`` alias."""

        index = "records"


def _ids_serializer(pid_fetcher=None, search_result=None):
    """Serialize the streamed hits as their sorted ids, naming the PID fetcher in a header."""
    return Response(
        " ".join(sorted(hit.meta.id for hit in search_result)),
        mimetype="text/plain",
        headers={"X-Pid-Fetcher": getattr(pid_fetcher, "__name__", "")},
    )


@pytest.fixture(scope="module")
def app_config(app_config):
    """Configure an export endpoint and the records-rest settings it reads."""
    app_config.update(
        RECORDS_REST_FACETS={},
        RECORDS_REST_SORT_OPTIONS={},
        RECORDS_REST_DEFAULT_SORT={},
        RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS={
            "record": {
                "list_route": "/records/",
                "list_permission_factory_imp": "invenio_records_rest.utils:allow_all",
                "pid_fetcher": "recid",
                "search_class": RecordSearch,
                "default_media_type": "text/plain",
                "search_serializers": {"text/plain": _ids_serializer},
            }
        },
    )
    return app_config


@pytest.fixture(scope="module")
def client(app):
    """Register the export blueprint and return a test client."""
    app.register_blueprint(create_blueprint_from_app(app))
    return app.test_client()


@pytest.fixture
def records(search_runner, new_index_name1):
    """Index the test records behind the ``records`` alias."""
    current_search_client.indices.create(index=new_index_name1, body={"aliases": {"records": {}}})
    for pid in range(RECORD_COUNT):
        current_search_client.index(index=new_index_name1, id=str(pid), body={"parity": ("even", "odd")[pid % 2]})
    current_search_client.indices.refresh(index=new_index_name1)


def test_export_streams_every_record(client, records):
    """Export returns every record, not only the first result page."""
    res = client.get("/export/records/")
    assert res.status_code == 200
    assert res.get_data(as_text=True).split() == sorted(str(pid) for pid in range(RECORD_COUNT))


def test_export_passes_the_pid_fetcher(client, records):
    """Serializers receive the endpoint's PID fetcher, as in the records-rest list view."""
    res = client.get("/export/records/")
    assert res.headers["X-Pid-Fetcher"] == "recid_fetcher"


def test_export_applies_the_query(client, records):
    """Export only streams the records matching the query string."""
    res = client.get("/export/records/", query_string={"q": "parity:odd"})
    assert res.status_code == 200
    assert res.get_data(as_text=True).split() == sorted(str(pid) for pid in range(1, RECORD_COUNT, 2))
