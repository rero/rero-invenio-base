# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Search dashboards objects: install them, and export the edited ones back."""

import json
import time
from importlib.resources import files

import requests

#: The search health dashboard, built on the `search-monitor-*` snapshots.
SEARCH_MONITOR_DASHBOARD_ID = "search-health"
SEARCH_MONITOR_NDJSON = files(__name__) / "search-monitor.ndjson"
HEADERS = {"osd-xsrf": "true"}


def dashboards_running(url, timeout=2):
    """Tell whether search dashboards answers at `url`.

    :param url: Dashboards base URL.
    :param timeout: seconds to wait for the answer.
    :returns: True when Dashboards answers.
    """
    try:
        return requests.get(f"{url}/api/status", timeout=timeout).ok
    except requests.RequestException:
        return False


def wait_for_dashboards(url, attempts=30, delay=2):
    """Wait until search dashboards answers at `url`.

    :param url: Dashboards base URL.
    :param attempts: number of tries.
    :param delay: seconds between two tries.
    :returns: True when Dashboards answered before the tries ran out.
    """
    for attempt in range(attempts):
        if dashboards_running(url):
            return True
        if attempt < attempts - 1:
            time.sleep(delay)
    return False


def install_objects(url, ndjson=SEARCH_MONITOR_NDJSON, meta_fields=None, index_patterns=None):
    """Import saved objects into search dashboards.

    :param url: Dashboards base URL.
    :param ndjson: NDJSON file of the saved objects.
    :param meta_fields: meta fields to set; Dashboards drops the fields starting with `_` that are not one.
    :param index_patterns: titles by id of index patterns to register, for Discover.
    :returns: number of imported objects.
    :raises requests.HTTPError: when Dashboards refuses a request.
    """
    if meta_fields:
        requests.post(
            f"{url}/api/opensearch-dashboards/settings",
            headers=HEADERS,
            json={"changes": {"metaFields": meta_fields}},
            timeout=30,
        ).raise_for_status()
    for pattern_id, title in (index_patterns or {}).items():
        response = requests.post(
            f"{url}/api/saved_objects/index-pattern/{pattern_id}",
            headers=HEADERS,
            json={"attributes": {"title": title, "timeFieldName": ""}},
            timeout=30,
        )
        # 409: registered by an earlier run
        if response.status_code != 409:
            response.raise_for_status()
    with ndjson.open("rb") as objects:
        response = requests.post(
            f"{url}/api/saved_objects/_import",
            params={"overwrite": "true"},
            headers=HEADERS,
            files={"file": (ndjson.name, objects, "application/ndjson")},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()["successCount"]


def export_dashboard(url, dashboard_id=SEARCH_MONITOR_DASHBOARD_ID, path=SEARCH_MONITOR_NDJSON):
    """Write a dashboard as edited in Dashboards, with everything it references, to `path`.

    :param url: Dashboards base URL.
    :param dashboard_id: id of the dashboard.
    :param path: NDJSON file to write.
    :returns: number of exported objects.
    :raises requests.HTTPError: when Dashboards refuses the export.
    """
    response = requests.post(
        f"{url}/api/saved_objects/_export",
        headers=HEADERS,
        json={"objects": [{"type": "dashboard", "id": dashboard_id}], "includeReferencesDeep": True},
        timeout=60,
    )
    response.raise_for_status()
    # The last line only counts the exported objects.
    lines = [line for line in response.text.splitlines() if line and "exportedCount" not in json.loads(line)]
    path.write_text("\n".join(lines))
    return len(lines)
