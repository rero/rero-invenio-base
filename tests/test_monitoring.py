# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the monitoring API, REST views and commands."""

import sys
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from click.testing import CliRunner
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_search import current_search_client
from redis import RedisError

from rero_invenio_base.cli.monitoring import (
    db_connection_counts_cli,
    search_db_missing,
)
from rero_invenio_base.cli.monitoring import (
    redis as redis_cli,
)
from rero_invenio_base.cli.monitoring import (
    search_db_counts as search_db_counts_cli,
)
from rero_invenio_base.cli.monitoring import (
    timestamps as timestamps_cli,
)
from rero_invenio_base.modules.monitoring import api, views
from rero_invenio_base.modules.monitoring.api import (
    Monitoring,
    db_connection_counts,
    db_connections,
    get_timestamp,
    get_timestamps,
    harvests,
    queues,
    redis_info,
    set_timestamp,
    settimestamp,
    snapshots,
)

INDEX = "monitoring-records"


@pytest.fixture
def records(app, db, search, monkeypatch):
    """Index `rec` records: 1 in both, 2 in the database only, 3 in the index only, 4 indexed twice.

    `rec_no_db` reads the same index, as a type without records in the database.
    """
    monkeypatch.setitem(
        app.config,
        "RERO_INVENIO_BASE_MONITORING_ENDPOINTS",
        {"rec": {"pid_type": "rec", "index": INDEX}, "rec_no_db": {"pid_type": "nodb", "index": INDEX}},
    )
    monkeypatch.setitem(app.config, "RERO_INVENIO_BASE_MONITORING_NO_DB", ["rec_no_db"])
    current_search_client.indices.delete(index=INDEX, ignore=[404])
    for pid in ("1", "2", "4"):
        PersistentIdentifier.create("rec", pid, status=PIDStatus.REGISTERED)
    db.session.commit()
    created = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    for doc_id, pid in (("a", "1"), ("b", "3"), ("c", "4"), ("d", "4")):
        current_search_client.index(index=INDEX, id=doc_id, body={"pid": pid, "_created": created})
    current_search_client.indices.refresh(index=INDEX)
    yield
    current_search_client.indices.delete(index=INDEX, ignore=[404])
    PersistentIdentifier.query.filter_by(pid_type="rec").delete()
    db.session.commit()


def test_monitoring_counts(records):
    """The counts and the differing pids of each type, the types without database counted in the index only."""
    monitoring = Monitoring(time_delta=0)
    info = monitoring.info()
    assert info["rec"] == {"index": INDEX, "db": 3, "search": 4, "db-search": -1}
    assert info["rec_no_db"] == {"index": INDEX, "db": 0, "search": 4, "db-search": 0}
    assert monitoring.get_search_db_missing_pids("rec") == (["3"], ["2"], ["4"])
    assert monitoring.missing("rec") == {"DB": ["3"], "search": ["2"], "search duplicate": ["4"]}
    assert monitoring.check() == {"rec": {"db-search": -1}}
    with pytest.raises(KeyError):
        monitoring.missing("unknown")


def test_monitoring_ignores_recent_records(records):
    """The records created during the delay are not counted."""
    assert Monitoring(time_delta=120).info()["rec"]["search"] == 0


def test_monitoring_difference_on_equal_counts(records, db):
    """With equal counts, the differing pids are listed."""
    PersistentIdentifier.create("rec", "5", status=PIDStatus.REGISTERED)
    db.session.commit()
    info = Monitoring(time_delta=0).info(difference_db_search=True)["rec"]
    assert info == {"index": INDEX, "db": 4, "search": 4, "db-search": 0, "db-": ["2", "5"], "search-": ["3"]}
    assert Monitoring(time_delta=0).check(difference_db_search=True) == {"rec": {"db-": 2, "search-": 1}}


def test_monitoring_missing_index(app, db, monkeypatch):
    """A missing index counts 0 documents."""
    monkeypatch.setitem(
        app.config, "RERO_INVENIO_BASE_MONITORING_ENDPOINTS", {"rec": {"pid_type": "rec", "index": "none"}}
    )
    assert Monitoring(time_delta=0).get_search_count("none") is None
    assert Monitoring(time_delta=0).info()["rec"] == {"index": "none", "db": 0, "search": 0, "db-search": 0}


def _execute(*answers):
    """Fake the database answers, one list of rows per query."""
    results = [
        mock.MagicMock(one=lambda rows=rows: rows[0], __iter__=lambda _, rows=rows: iter(rows)) for rows in answers
    ]
    return mock.patch.object(api.db.session, "execute", side_effect=results)


COUNTS = ([(100, 10, 3, 87)], [(2, 4000, 123)])
COUNTS_DATA = {
    "max": 100,
    "used": 10,
    "reserved_for_super": 3,
    "free": 87,
    "idle_in_transaction": 2,
    "oldest_transaction": 4000,
    "size": 123,
}


def test_db_connections(app):
    """The connection counts and the connection details by backend pid."""
    with _execute(*COUNTS):
        assert db_connection_counts() == COUNTS_DATA
    row = (42, "app", "10.0.0.1", 5432, "b", "x", "q", None, "active", "SELECT 1")
    with _execute([row]):
        assert db_connections() == {
            42: dict(zip(api.DB_CONNECTION_FIELDS, row[1:])),
        }


def test_redis_info(app, monkeypatch):
    """Each instance with a Redis URL is reported, a failing one with its error."""
    monkeypatch.setitem(
        app.config,
        "RERO_INVENIO_BASE_MONITORING_REDIS",
        {"sessions": "SESSIONS_URL", "cache": "CACHE_URL", "none": "NO_URL"},
    )
    monkeypatch.setitem(app.config, "SESSIONS_URL", "redis://sessions")
    monkeypatch.setitem(app.config, "CACHE_URL", "redis://cache")

    class Client:
        def __init__(self, url):
            self.url = url

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def info(self):
            if self.url == "redis://cache":
                raise RedisError("down")
            return {"redis_version": "8"}

    monkeypatch.setattr(api.Redis, "from_url", Client)
    assert redis_info() == {
        "sessions": {"name": "sessions", "redis_version": "8"},
        "cache": {"name": "cache", "status": "error", "error": "down"},
    }


def test_timestamps(app):
    """The recorded events keep their details, with the time as text and as Unix time."""

    @settimestamp
    def harvest():
        return 3

    set_timestamp("claims-creation", count=2)
    assert harvest() == 3
    assert get_timestamp("claims-creation")["count"] == 2
    assert get_timestamp("unknown") is None
    events = get_timestamps()
    assert events["claims_creation"]["name"] == "claims-creation"
    assert events["harvest"]["result"] == 3
    utctime = datetime.strptime(events["harvest"]["utctime"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=UTC)
    assert events["harvest"]["unixtime"] == int(utctime.timestamp())
    assert 0 <= events["harvest"]["age"] < 60


@pytest.fixture
def monitoring_user(monkeypatch):
    """Let the requests in as the monitoring role, or as a given user."""
    user = SimpleNamespace(is_authenticated=True, allowed=True)
    monkeypatch.setattr(views, "current_user", user)
    monkeypatch.setattr(views, "Permission", lambda need: SimpleNamespace(can=lambda: user.allowed))
    return user


def test_views_permission(client, monitoring_user):
    """Anonymous requests get a 401, the users without the monitoring role a 403."""
    monitoring_user.is_authenticated = False
    assert client.get("/monitoring/search").status_code == 401
    monitoring_user.is_authenticated, monitoring_user.allowed = True, False
    assert client.get("/monitoring/search_db_counts").status_code == 403


def test_views_counts(client, records, monitoring_user):
    """The counts, their check and the missing pids, as Zabbix reads them."""
    res = client.get("/monitoring/search_db_counts?delay=0")
    assert res.json["data"]["rec"] == {"index": INDEX, "db": 3, "search": 4, "db-search": -1}
    res = client.get("/monitoring/check_search_db_counts?delay=0")
    assert res.json["data"] == {"status": "red"}
    (error,) = res.json["errors"]
    assert error["code"] == "DB_SEARCH_COUNTER_MISMATCH"
    assert error["details"] == "There are 1 items from rec missing in DB."
    assert error["links"]["rec"] == "http://localhost/monitoring/missing_pids/rec"
    res = client.get("/monitoring/missing_pids/rec?delay=0")
    assert res.json == {"data": {"DB": ["3"], "search": ["2"], "search duplicate": ["4"]}}
    res = client.get("/monitoring/missing_pids/unknown")
    assert res.status_code == 404
    assert res.json["error"]["code"] == "DOCUMENT_TYPE_NOT_FOUND"


def test_views_green(client, app, db, search, monitoring_user, monkeypatch):
    """Without differences, the check is green."""
    monkeypatch.setitem(app.config, "RERO_INVENIO_BASE_MONITORING_ENDPOINTS", {})
    assert client.get("/monitoring/check_search_db_counts").json == {"data": {"status": "green"}}


def test_views_services(client, app, monitoring_user, monkeypatch):
    """The database, search, Redis and timestamp routes wrap their data."""
    with _execute(*COUNTS):
        res = client.get("/monitoring/db_connection_counts")
    assert res.json == {"data": COUNTS_DATA}
    monkeypatch.setattr(views, "search_health", lambda: {"status": "green"})
    assert client.get("/monitoring/search").json == {"data": {"status": "green"}}
    monkeypatch.setattr(views, "search_indices", lambda: {"records": {"index": "records"}})
    assert client.get("/monitoring/search_indices").json == {"data": {"records": {"index": "records"}}}
    monkeypatch.setattr(views, "redis_info", lambda: {"sessions": {"name": "sessions"}})
    assert client.get("/monitoring/redis").json == {"data": {"sessions": {"name": "sessions"}}}
    set_timestamp("sync")
    assert client.get("/monitoring/timestamps").json["data"]["sync"]["name"] == "sync"


def test_views_database_error(client, monitoring_user):
    """A database error is answered with a 500."""
    with mock.patch.object(api.db.session, "execute", side_effect=api.db.exc.SQLAlchemyError("gone")):
        res = client.get("/monitoring/db_connection_counts")
    assert res.status_code == 500
    assert res.json["error"]["code"] == "DATABASE_ERROR"


def test_cli(app, records, monkeypatch):
    """The commands print the counts, the missing pids, the connections, Redis and the events."""
    res = CliRunner().invoke(search_db_counts_cli, ["-d", "0", "-m"])
    assert res.exit_code == 0, res.output
    assert "rec missing in DB: 3" in res.output
    res = CliRunner().invoke(search_db_missing, ["unknown"])
    assert res.exit_code == 1
    assert "Document type not found: unknown" in res.output
    with _execute(*COUNTS):
        res = CliRunner().invoke(db_connection_counts_cli)
    assert res.output.startswith("max: 100, used: 10, reserved_for_super: 3, free: 87, idle_in_transaction: 2")
    monkeypatch.setattr(sys.modules[redis_cli.callback.__module__], "redis_info", lambda: {"cache": {"name": "cache"}})
    assert "[cache]" in CliRunner().invoke(redis_cli).output
    set_timestamp("sync", count=1)
    assert ": sync count=1 | name=sync" in CliRunner().invoke(timestamps_cli).output


def test_snapshots(app, monkeypatch):
    """The last successful and failed snapshots of each repository, with their age, and the policies."""
    now = int(datetime.now(UTC).timestamp())
    rows = [
        {"id": "daily-1", "status": "SUCCESS", "end_epoch": str(now - 7200)},
        {"id": "daily-2", "status": "FAILED", "end_epoch": str(now - 3600)},
        {"id": "daily-3", "status": "IN_PROGRESS", "end_epoch": "0"},
    ]
    client = mock.MagicMock()
    client.snapshot.get_repository.return_value = {"prod": {}, "empty": {}}
    client.cat.snapshots.side_effect = lambda repository, **_: rows if repository == "prod" else []
    client.transport.perform_request.return_value = {"policies": [{"_id": "daily", "sm_policy": {"enabled": True}}]}
    monkeypatch.setattr(api, "current_search_client", client)
    data = snapshots()
    prod = data["repositories"]["prod"]
    assert (prod["count"], prod["last_success"], prod["last_failure"]) == (3, "daily-1", "daily-2")
    assert 7200 <= prod["last_success_age"] < 7260
    assert data["repositories"]["empty"]["last_success_age"] is None
    assert data["policies"] == {"daily": {"name": "daily", "enabled": True}}
    client.transport.perform_request.side_effect = api.search.NotFoundError(404, "no plugin", {})
    assert snapshots()["policies"] == {}


def test_queues(app, monkeypatch):
    """The Celery, indexer and configured queues known to the broker, with their messages and consumers."""
    monkeypatch.setitem(app.config, "RERO_INVENIO_BASE_MONITORING_QUEUES", ["bulk_index", "unknown"])
    monkeypatch.setitem(app.config, "INDEXER_MQ_QUEUE", SimpleNamespace(name="indexer"))
    depths = {"celery": (0, 4), "indexer": (2235, 0), "bulk_index": (0, 6)}

    class Channel:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def queue_declare(self, name, passive):
            if name not in depths:
                raise KeyError(name)
            return SimpleNamespace(message_count=depths[name][0], consumer_count=depths[name][1])

    connection = mock.MagicMock(channel=Channel, channel_errors=(KeyError,))
    connection.__enter__.return_value = connection
    celery = SimpleNamespace(conf=SimpleNamespace(task_default_queue="celery", task_queues=None))
    celery.connection = lambda: connection
    monkeypatch.setattr(api, "celery_app", celery)
    assert queues() == {name: {"name": name, "messages": m, "consumers": c} for name, (m, c) in depths.items()}


def test_harvests(app, monkeypatch):
    """The last run of each OAI source, nothing without invenio-oaiharvester."""
    lastrun = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2)
    sources = [SimpleNamespace(name="agents.gnd", lastrun=lastrun), SimpleNamespace(name="new", lastrun=None)]
    models = SimpleNamespace(OAIHarvestConfig=SimpleNamespace(query=SimpleNamespace(all=lambda: sources)))
    monkeypatch.setitem(sys.modules, "invenio_oaiharvester.models", models)
    data = harvests()
    assert data["agents.gnd"]["lastrun"] == lastrun.isoformat()
    assert 172800 <= data["agents.gnd"]["age"] < 172860
    assert data["new"] == {"name": "new", "lastrun": None, "age": None}
    monkeypatch.setitem(sys.modules, "invenio_oaiharvester.models", None)
    assert harvests() == {}


def test_views_watch(client, monitoring_user, monkeypatch):
    """The snapshot, queue and harvest routes wrap their data."""
    for name in ("snapshots", "queues", "harvests"):
        monkeypatch.setattr(views, name, lambda name=name: {name: {}})
        assert client.get(f"/monitoring/{name}").json == {"data": {name: {}}}
