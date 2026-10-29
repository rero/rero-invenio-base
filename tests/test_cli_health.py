# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli health command."""

import re
import sys
from contextlib import contextmanager
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from opensearchpy.exceptions import ConnectionError as SearchConnectionError

from rero_invenio_base.cli.health import health


@pytest.fixture
def broker(monkeypatch):
    """Replace the celery broker connection with one that always connects."""

    @contextmanager
    def connection():
        yield SimpleNamespace(ensure_connection=lambda max_retries: None)

    monkeypatch.setattr("celery.current_app", SimpleNamespace(connection=connection))


def _fail(*args, **kwargs):
    raise SearchConnectionError("N/A", "connection refused", None)


def test_health_reports_every_service(app, search, broker, monkeypatch):
    """Health reports the live search cluster and hides the broker credentials."""
    monkeypatch.setitem(app.config, "BROKER_URL", "amqp://guest:secret@mq:5672//")
    res = CliRunner().invoke(health)
    assert res.exit_code == 0
    assert re.search(r"SEARCH\s+OK\s+(GREEN|YELLOW) — 1 node\(s\), cluster: \S+", res.output)
    assert re.search(r"Database\s+OK", res.output)
    assert re.search(r"Broker\s+OK\s+amqp://mq:5672//", res.output)
    assert "secret" not in res.output


@pytest.mark.parametrize(
    ("cluster_health", "expected"),
    [
        (lambda: {"status": "red", "number_of_nodes": 1, "cluster_name": "c"}, r"SEARCH\s+ERROR\s+RED — 1 node\(s\)"),
        (_fail, r"SEARCH\s+ERROR\s+ConnectionError"),
    ],
    ids=["red", "unreachable"],
)
def test_health_search_failure_exits_1(app, broker, monkeypatch, cluster_health, expected):
    """A red or unreachable search cluster makes health exit 1."""
    health_cli = sys.modules[health.callback.__module__]
    monkeypatch.setattr(
        health_cli, "current_search_client", SimpleNamespace(cluster=SimpleNamespace(health=cluster_health))
    )
    res = CliRunner().invoke(health)
    assert res.exit_code == 1
    assert re.search(expected, res.output)
