# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the search health snapshot task."""

import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from rero_invenio_base.modules.monitoring.tasks import _last_snapshot, _rate, index_search_stats

_NODE_STATS = {
    "name": "search-node-1",
    "jvm": {
        "mem": {
            "heap_used_percent": 45,
            "heap_used_in_bytes": 512 * 1024 * 1024,
            "heap_max_in_bytes": 1024 * 1024 * 1024,
        },
        "gc": {"collectors": {"old": {"collection_count": 5, "collection_time_in_millis": 200}}},
    },
    "os": {"cpu": {"percent": 12}, "mem": {"used_percent": 60}},
    "fs": {"total": {"total_in_bytes": 1_000_000, "free_in_bytes": 600_000}},
    "indices": {
        "docs": {"count": 100_000, "deleted": 50},
        "store": {"size_in_bytes": 512_000},
        "search": {
            "query_total": 500,
            "query_time_in_millis": 1200,
            "fetch_total": 300,
        },
        "indexing": {
            "index_total": 800,
            "index_time_in_millis": 400,
            "index_failed": 2,
        },
    },
}


def _make_client(search_hits=None, raise_on_search=False):
    """Return a mock search client for task tests."""
    client = MagicMock()
    client.cluster.health.return_value = {
        "status": "green",
        "active_shards": 10,
        "active_primary_shards": 5,
        "unassigned_shards": 0,
        "relocating_shards": 0,
        "initializing_shards": 0,
        "number_of_nodes": 1,
    }
    client.nodes.stats.return_value = {"nodes": {"node1": _NODE_STATS}}
    if raise_on_search:
        client.search.side_effect = RuntimeError("search unreachable")
    else:
        hits = search_hits if search_hits is not None else []
        client.search.return_value = {"hits": {"hits": hits}}
    return client


# --- _last_snapshot ----------------------------------------------------------


def test_last_snapshot_returns_source_when_hit_found():
    """Returns _source of first hit when results are present."""
    src = {"@timestamp": "2026-01-01T00:00:00.000Z", "node": {"indices": {}}}
    client = _make_client(search_hits=[{"_source": src}])
    result = _last_snapshot(client, "node1")
    assert result == src


def test_last_snapshot_returns_none_when_no_hits():
    """Returns None when the search result has no hits."""
    client = _make_client(search_hits=[])
    assert _last_snapshot(client, "node1") is None


def test_last_snapshot_returns_none_and_logs_on_exception(caplog):
    """Returns None and logs the exception when the search call fails."""
    client = _make_client(raise_on_search=True)
    with caplog.at_level(logging.ERROR, logger="rero_invenio_base.modules.monitoring.tasks"):
        result = _last_snapshot(client, "node1")
    assert result is None
    assert "node1" in caplog.text


# --- _rate -------------------------------------------------------------------


def test_rate_zero_when_no_prev_src():
    """Rate is 0 when there is no previous snapshot (first run)."""
    assert _rate(100, None, "search_query_total", 60) == 0.0


def test_rate_computed_correctly():
    """Rate equals delta / elapsed for a normal transition."""
    prev_src = {"node": {"indices": {"search_query_total": 400}}}
    # (500 - 400) / 60 = 1.6667
    assert _rate(500, prev_src, "search_query_total", 60) == round(100 / 60, 4)


def test_rate_clamped_to_zero_on_negative_delta():
    """Rate is never negative (counter reset / node restart)."""
    prev_src = {"node": {"indices": {"index_total": 1000}}}
    assert _rate(50, prev_src, "index_total", 60) == 0.0


def test_rate_uses_one_when_elapsed_is_zero():
    """elapsed=0 falls back to 1 to avoid division by zero."""
    prev_src = {"node": {"indices": {"index_total": 0}}}
    assert _rate(60, prev_src, "index_total", 0) == 60.0


def test_rate_zero_when_field_missing_in_prev():
    """Missing field in prev_src defaults to current → rate 0."""
    prev_src = {"node": {"indices": {}}}
    assert _rate(200, prev_src, "search_query_total", 60) == 0.0


# --- index_search_stats ----------------------------------------------------------


def test_index_search_stats_first_run_indexes_document():
    """On first run (no snapshot) the task writes one document per node."""
    client = _make_client(search_hits=[])
    with patch("rero_invenio_base.modules.monitoring.tasks.current_search_client", client):
        index_search_stats()
    assert client.index.call_count == 1
    call_kwargs = client.index.call_args
    index_name = call_kwargs[1]["index"] if call_kwargs[1] else call_kwargs[0][0]
    assert index_name.startswith("search-monitor-")


def test_index_search_stats_document_structure():
    """Indexed document contains all expected top-level and nested keys."""
    client = _make_client(search_hits=[])
    with patch("rero_invenio_base.modules.monitoring.tasks.current_search_client", client):
        index_search_stats()
    doc = client.index.call_args[1]["body"]
    assert "@timestamp" in doc
    assert doc["cluster"]["status"] == "green"
    assert doc["cluster"]["status_code"] == 0
    node = doc["node"]
    assert node["id"] == "node1"
    assert "jvm" in node
    assert "system" in node
    assert "fs" in node
    indices = node["indices"]
    assert "search_queries_per_sec" in indices
    assert "index_ops_per_sec" in indices
    assert "index_failures_per_sec" in indices
    assert indices["search_queries_per_sec"] == 0.0
    assert indices["index_ops_per_sec"] == 0.0


def test_index_search_stats_rates_computed_from_prev_snapshot():
    """Rates are non-zero when a previous snapshot provides a baseline."""
    prev_ts = (datetime.now(UTC) - timedelta(seconds=60)).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    prev_src = {
        "@timestamp": prev_ts,
        "node": {
            "indices": {
                "search_query_total": 400,
                "index_total": 700,
                "index_failed_total": 1,
            }
        },
    }
    client = _make_client(search_hits=[{"_source": prev_src}])
    with patch("rero_invenio_base.modules.monitoring.tasks.current_search_client", client):
        index_search_stats()
    indices = client.index.call_args[1]["body"]["node"]["indices"]
    assert indices["search_queries_per_sec"] > 0
    assert indices["index_ops_per_sec"] > 0
    assert indices["index_failures_per_sec"] > 0


@pytest.mark.parametrize("status,code", [("green", 0), ("yellow", 1), ("red", 2)])
def test_index_search_stats_cluster_status_code(status, code):
    """status_code is mapped correctly for all three cluster health states."""
    client = _make_client(search_hits=[])
    client.cluster.health.return_value = {
        "status": status,
        "active_shards": 1,
        "active_primary_shards": 1,
        "unassigned_shards": 0,
        "relocating_shards": 0,
        "initializing_shards": 0,
        "number_of_nodes": 1,
    }
    with patch("rero_invenio_base.modules.monitoring.tasks.current_search_client", client):
        index_search_stats()
    doc = client.index.call_args[1]["body"]
    assert doc["cluster"]["status"] == status
    assert doc["cluster"]["status_code"] == code
