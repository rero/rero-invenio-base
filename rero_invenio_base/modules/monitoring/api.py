# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Monitoring of the database, the search engine, Redis and the scheduled tasks."""

import calendar
from collections import Counter
from datetime import UTC, datetime, timedelta
from functools import wraps

from celery import current_app as celery_app
from flask import current_app
from invenio_cache import current_cache
from invenio_db import db
from invenio_pidstore.models import PersistentIdentifier, PIDStatus
from invenio_search import current_search_client
from invenio_search.api import RecordsSearch
from invenio_search.engine import search
from redis import Redis, RedisError
from sqlalchemy import func, text

DB_CONNECTION_COUNTS_QUERY = """
    select max_conn, used, res_for_super, max_conn-used-res_for_super free
    from (select count(*) used from pg_stat_activity) t1,
         (select setting::int res_for_super from pg_settings where name=$$superuser_reserved_connections$$) t2,
         (select setting::int max_conn from pg_settings where name=$$max_connections$$) t3
"""

DB_CONNECTIONS_QUERY = """
    SELECT pid, application_name, client_addr, client_port, backend_start,
           xact_start, query_start, wait_event, state, left(query, 64)
    FROM pg_stat_activity ORDER BY query_start DESC
"""

DB_TRANSACTIONS_QUERY = """
    select count(*) filter (where state like 'idle in transaction%'),
           coalesce(max(extract(epoch from now() - xact_start)), 0)::int,
           pg_database_size(current_database())
    from pg_stat_activity where datname = current_database()
"""

DB_CONNECTION_FIELDS = (
    "application_name",
    "client_addr",
    "client_port",
    "backend_start",
    "xact_start",
    "query_start",
    "wait_event",
    "state",
    "left",
)


def db_connection_counts():
    """Count the PostgreSQL connections, and describe the transactions of the database.

    :returns: maximum, used, reserved for superusers and free connections, the
        connections idle in a transaction, the age in seconds of the oldest open
        transaction and the database size in bytes.
    """
    max_conn, used, reserved, free = db.session.execute(text(DB_CONNECTION_COUNTS_QUERY)).one()
    idle_in_transaction, oldest_transaction, size = db.session.execute(text(DB_TRANSACTIONS_QUERY)).one()
    return {
        "max": max_conn,
        "used": used,
        "reserved_for_super": reserved,
        "free": free,
        "idle_in_transaction": idle_in_transaction,
        "oldest_transaction": oldest_transaction,
        "size": size,
    }


def db_connections():
    """Describe the PostgreSQL connections, the most recent query first.

    :returns: the connection details by backend pid.
    """
    return {row[0]: dict(zip(DB_CONNECTION_FIELDS, row[1:])) for row in db.session.execute(text(DB_CONNECTIONS_QUERY))}


def search_health():
    """Return the health of the search cluster."""
    return current_search_client.cluster.health()


def search_indices():
    """Describe the search indices, sizes in bytes.

    :returns: the `cat indices` row by index name.
    """
    rows = current_search_client.cat.indices(bytes="b", format="json", s="index")
    return {row["index"]: row for row in rows}


def _age(epoch):
    """Return the seconds elapsed since a Unix time."""
    return int(datetime.now(UTC).timestamp() - epoch)


def snapshots():
    """Describe the snapshots of each repository and the snapshot management policies.

    :returns: by repository, the snapshot count and the last successful and
        failed snapshots with their age in seconds; by policy, whether it is enabled.
    """
    repositories = {}
    for name in current_search_client.snapshot.get_repository():
        rows = current_search_client.cat.snapshots(repository=name, format="json", s="end_epoch")
        repository = {"name": name, "count": len(rows), "last_success": None, "last_success_age": None}
        repository |= {"last_failure": None, "last_failure_age": None}
        for row in rows:
            state = "success" if row["status"] == "SUCCESS" else "failure"
            if row["status"] != "IN_PROGRESS":
                repository[f"last_{state}"] = row["id"]
                repository[f"last_{state}_age"] = _age(int(row["end_epoch"]))
        repositories[name] = repository
    try:
        answer = current_search_client.transport.perform_request("GET", "/_plugins/_sm/policies")
        policies = {
            policy["_id"]: {"name": policy["_id"], "enabled": policy["sm_policy"].get("enabled", False)}
            for policy in answer.get("policies", [])
        }
    except search.NotFoundError:
        policies = {}
    return {"repositories": repositories, "policies": policies}


def queues():
    """Count the messages and consumers of the Celery queues, the indexing queue included.

    The queues are the default and the declared Celery queues, the indexer queue
    and `RERO_INVENIO_BASE_MONITORING_QUEUES`. A queue unknown to the broker is skipped.

    :returns: messages and consumers by queue name.
    """
    names = {celery_app.conf.task_default_queue or "celery"}
    names |= {getattr(queue, "name", str(queue)) for queue in celery_app.conf.task_queues or []}
    if indexer_queue := current_app.config.get("INDEXER_MQ_QUEUE"):
        names.add(indexer_queue.name)
    names |= set(current_app.config["RERO_INVENIO_BASE_MONITORING_QUEUES"])
    counts = {}
    with celery_app.connection() as connection:
        for name in sorted(names):
            # a passive declaration of an unknown queue closes its channel
            with connection.channel() as channel:
                try:
                    declared = channel.queue_declare(name, passive=True)
                except connection.channel_errors:
                    continue
            counts[name] = {"name": name, "messages": declared.message_count, "consumers": declared.consumer_count}
    return counts


def harvests():
    """Describe the last run of each OAI harvest source.

    :returns: by source, the date of its last run and its age in seconds; empty
        without invenio-oaiharvester.
    """
    try:
        from invenio_oaiharvester.models import OAIHarvestConfig  # optional dependency, installed by rero-mef and sonar
    except ImportError:
        return {}
    return {
        source.name: {
            "name": source.name,
            "lastrun": source.lastrun.isoformat() if source.lastrun else None,
            "age": _age(source.lastrun.replace(tzinfo=source.lastrun.tzinfo or UTC).timestamp())
            if source.lastrun
            else None,
        }
        for source in OAIHarvestConfig.query.all()
    }


def redis_info():
    """Return the information of each configured Redis instance.

    The instances are given by `RERO_INVENIO_BASE_MONITORING_REDIS`, a name by
    config key holding the Redis URL. Instances without a Redis URL are skipped.

    :returns: the Redis `INFO` by instance name, or an error status.
    """
    info = {}
    for name, config_key in current_app.config["RERO_INVENIO_BASE_MONITORING_REDIS"].items():
        url = current_app.config.get(config_key)
        if not url or not url.startswith(("redis://", "rediss://", "unix://")):
            continue
        try:
            with Redis.from_url(url) as client:
                info[name] = {"name": name, **client.info()}
        except RedisError as error:
            info[name] = {"name": name, "status": "error", "error": str(error)}
    return info


def set_timestamp(name, **kwargs):
    """Record the time of an event, with optional details, in the cache.

    :param name: name of the event.
    :param kwargs: details to keep with the time.
    :returns: the recorded time.
    """
    time = datetime.now(UTC)
    timestamps = current_cache.get("timestamps") or {}
    timestamps[name] = kwargs | {"time": time, "name": name}
    if not current_cache.set(key="timestamps", value=timestamps, timeout=0):
        current_app.logger.warning(f"Can not set timestamp: {name}")
    return time


def get_timestamp(name):
    """Return the recorded event, without its name.

    :param name: name of the event.
    :returns: the time and details of the event, or None.
    """
    if timestamp := (current_cache.get("timestamps") or {}).get(name):
        return {key: value for key, value in timestamp.items() if key != "name"}
    return None


def get_timestamps():
    """Return every recorded event, with its time as text and as Unix time.

    :returns: the events by name, `-` replaced by `_` in the names.
    """
    timestamps = {}
    for name, value in (current_cache.get("timestamps") or {}).items():
        event = {key: data for key, data in value.items() if key != "time"}
        event["utctime"] = value["time"].strftime("%Y-%m-%d %H:%M:%S")
        event["unixtime"] = calendar.timegm(value["time"].utctimetuple())
        event["age"] = _age(event["unixtime"])
        timestamps[name.replace("-", "_")] = event
    return timestamps


def settimestamp(func):
    """Record the time and result of each call of the decorated function."""

    @wraps(func)
    def wrapped(*args, **kwargs):
        result = func(*args, **kwargs)
        set_timestamp(func.__name__, result=result)
        return result

    return wrapped


class Monitoring:
    """Compare the records of the database with the documents of the search engine."""

    def __init__(self, time_delta=1):
        """Ignore the records created during the last minutes, which may not be indexed yet.

        :param time_delta: number of minutes to ignore.
        """
        self.date = datetime.now(UTC) - timedelta(minutes=int(time_delta))
        self._db_counts = {}

    @staticmethod
    def endpoints():
        """Return the indexed record types.

        They are the `RECORDS_REST_ENDPOINTS` with a search index, the endpoint
        key being the pid type, completed or overridden by
        `RERO_INVENIO_BASE_MONITORING_ENDPOINTS`.

        :returns: the pid type and the index by record type.
        """
        endpoints = {
            doc_type: {"pid_type": endpoint.get("pid_type", doc_type), "index": endpoint["search_index"]}
            for doc_type, endpoint in current_app.config.get("RECORDS_REST_ENDPOINTS", {}).items()
            if endpoint.get("search_index")
        }
        return endpoints | current_app.config["RERO_INVENIO_BASE_MONITORING_ENDPOINTS"]

    @staticmethod
    def has_db(doc_type):
        """Tell whether the records of a type are kept in the database."""
        return doc_type not in current_app.config["RERO_INVENIO_BASE_MONITORING_NO_DB"]

    def _db_pids(self, pid_type, with_deleted=False):
        query = PersistentIdentifier.query.filter_by(pid_type=pid_type).filter(PersistentIdentifier.created < self.date)
        if not with_deleted:
            query = query.filter_by(status=PIDStatus.REGISTERED)
        return query

    def get_db_count(self, pid_type, with_deleted=False):
        """Count the records of a pid type in the database.

        All pid types are counted by one grouped query, run once per instance: on
        tens of millions of pids it is three times faster than a count per type.

        :param pid_type: pid type of the records.
        :param with_deleted: count the deleted records too.
        :returns: the number of records.
        """
        if with_deleted not in self._db_counts:
            query = db.session.query(PersistentIdentifier.pid_type, func.count()).filter(
                PersistentIdentifier.created < self.date
            )
            if not with_deleted:
                query = query.filter(PersistentIdentifier.status == PIDStatus.REGISTERED)
            self._db_counts[with_deleted] = dict(query.group_by(PersistentIdentifier.pid_type).all())
        return self._db_counts[with_deleted].get(pid_type, 0)

    def _search(self, index):
        return RecordsSearch(index=index).filter("range", _created={"lte": self.date})

    def get_search_count(self, index):
        """Count the documents of an index.

        :param index: index or alias name.
        :returns: the number of documents, or None when the index does not exist.
        """
        try:
            return self._search(index).count()
        except search.NotFoundError:
            return None

    def get_search_db_missing_pids(self, doc_type, with_deleted=False):
        """Compare the pids of the index with the ones of the database.

        The index is read in pages of 10,000 and the database in one query.

        :param doc_type: record type.
        :param with_deleted: take the deleted records of the database too.
        :returns: (pids only in the index, pids only in the database, pids indexed more than once).
        """
        endpoint = self.endpoints()[doc_type]
        search_pids = Counter()
        for hit in self._search(endpoint["index"]).source(["pid", "id"]).params(size=10000).scan():
            # records-resources records keep their pid in `id`
            search_pids[hit.pid if isinstance(getattr(hit, "pid", None), str) else hit.id] += 1
        db_pids = set()
        if self.has_db(doc_type):
            query = self._db_pids(endpoint["pid_type"], with_deleted).with_entities(PersistentIdentifier.pid_value)
            db_pids = {pid for (pid,) in query.yield_per(10000)}
        return (
            sorted(search_pids.keys() - db_pids),
            sorted(db_pids - search_pids.keys()),
            sorted(pid for pid, count in search_pids.items() if count > 1),
        )

    def info(self, with_deleted=False, difference_db_search=False):
        """Count the records of each type in the database and in the index.

        :param with_deleted: count the deleted records of the database too.
        :param difference_db_search: list the differing pids of the types whose counts are equal.
        :returns: by record type, the index, the counts and their difference.
        """
        info = {}
        for doc_type, endpoint in self.endpoints().items():
            db_count = self.get_db_count(endpoint["pid_type"], with_deleted) if self.has_db(doc_type) else 0
            search_count = self.get_search_count(endpoint["index"])
            data = {"index": endpoint["index"], "db": db_count, "search": search_count or 0}
            data["db-search"] = db_count - data["search"] if self.has_db(doc_type) else 0
            if difference_db_search and data["db-search"] == 0 and self.has_db(doc_type) and search_count is not None:
                search_only, db_only, _ = self.get_search_db_missing_pids(doc_type, with_deleted)
                if db_only:
                    data["db-"] = db_only
                if search_only:
                    data["search-"] = search_only
            info[doc_type] = data
        return info

    def check(self, with_deleted=False, difference_db_search=False):
        """Return the record types whose database and index differ.

        :param with_deleted: count the deleted records of the database too.
        :param difference_db_search: compare the pids of the types whose counts are equal.
        :returns: by record type, the count difference and the numbers of differing pids.
        """
        checks = {}
        for doc_type, data in self.info(with_deleted, difference_db_search).items():
            check = {key: len(data[key]) for key in ("db-", "search-") if key in data}
            if data["db-search"]:
                check["db-search"] = data["db-search"]
            if check:
                checks[doc_type] = check
        return checks

    def missing(self, doc_type, with_deleted=False):
        """List the pids missing in the database or in the index.

        :param doc_type: record type.
        :param with_deleted: take the deleted records of the database too.
        :returns: the pids missing in the database, missing in the index and indexed more than once.
        :raises KeyError: when the record type is not indexed.
        """
        search_only, db_only, duplicates = self.get_search_db_missing_pids(doc_type, with_deleted)
        return {"DB": search_only, "search": db_only, "search duplicate": duplicates}
