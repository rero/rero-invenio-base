# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic backend libraries for RERO Invenio instances."""

#: Role allowed to read the monitoring REST API, beside the superusers.
RERO_INVENIO_BASE_MONITORING_ROLE = "monitoring"

#: Redis instances of the monitoring: the config key holding the Redis URL, by instance name.
RERO_INVENIO_BASE_MONITORING_REDIS = {"sessions": "ACCOUNTS_SESSION_REDIS_URL"}

#: Queues to watch beside the Celery queues and the indexer queue, e.g. a queue of dedicated indexing workers.
RERO_INVENIO_BASE_MONITORING_QUEUES = []

#: Indexed record types missing from `RECORDS_REST_ENDPOINTS`, or overriding them:
#: `{record type: {"pid_type": pid type, "index": index or alias}}`.
RERO_INVENIO_BASE_MONITORING_ENDPOINTS = {}

#: Indexed record types without records in the database, counted in the index only.
RERO_INVENIO_BASE_MONITORING_NO_DB = []

#: Search dashboards URL, where the search health dashboard is installed.
RERO_INVENIO_BASE_MONITORING_DASHBOARDS_URL = "http://localhost:5601"
