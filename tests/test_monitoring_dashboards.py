# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the search dashboards install and export of the search health dashboard."""

import json
from unittest import mock

import pytest
import requests
from click.testing import CliRunner

from rero_invenio_base.cli.monitoring import dashboards as dashboards_cli
from rero_invenio_base.modules.monitoring import dashboards
from rero_invenio_base.modules.monitoring.dashboards import (
    SEARCH_MONITOR_DASHBOARD_ID,
    SEARCH_MONITOR_NDJSON,
    dashboards_running,
    export_dashboard,
    install_objects,
    wait_for_dashboards,
)

URL = "http://dashboards:5601"


def response(status=200, payload=None, text=""):
    """Build a Dashboards answer."""
    res = requests.Response()
    res.status_code = status
    res._content = json.dumps(payload).encode() if payload is not None else text.encode()
    return res


def test_bundled_dashboard_is_consistent():
    """Every panel, visualization and field the dashboard needs is in the NDJSON."""
    objects = {obj["id"]: obj for obj in map(json.loads, SEARCH_MONITOR_NDJSON.read_text().splitlines())}
    dashboard = objects[SEARCH_MONITOR_DASHBOARD_ID]
    panels = json.loads(dashboard["attributes"]["panelsJSON"])
    references = {ref["name"]: ref["id"] for ref in dashboard["references"]}
    assert {panel["panelRefName"] for panel in panels} == set(references)
    fields = {
        obj["id"]: {field["name"] for field in json.loads(obj["attributes"]["fields"])}
        for obj in objects.values()
        if obj["type"] == "index-pattern"
    }
    for vis_id in references.values():
        vis = objects[vis_id]
        pattern = vis["references"][0]["id"]
        for agg in json.loads(vis["attributes"]["visState"])["aggs"]:
            if field := agg["params"].get("field"):
                assert field in fields[pattern], f"{vis_id}: {field}"


@pytest.mark.parametrize(
    ("side_effect", "expected"),
    [(response(200), True), (response(503), False), (requests.ConnectionError(), False)],
)
def test_dashboards_running(side_effect, expected):
    """Only a successful status answer counts as running."""
    with mock.patch.object(dashboards.requests, "get", side_effect=[side_effect]):
        assert dashboards_running(URL) is expected


def test_wait_for_dashboards():
    """Waiting stops at the first answer, and gives up after the last try."""
    with (
        mock.patch.object(dashboards, "dashboards_running", side_effect=[False, True]) as running,
        mock.patch.object(dashboards.time, "sleep") as sleep,
    ):
        assert wait_for_dashboards(URL, attempts=3)
    assert running.call_count == 2
    sleep.assert_called_once()
    with (
        mock.patch.object(dashboards, "dashboards_running", return_value=False),
        mock.patch.object(dashboards.time, "sleep") as sleep,
    ):
        assert not wait_for_dashboards(URL, attempts=3)
    assert sleep.call_count == 2


def test_install_objects():
    """The meta fields come first, an index pattern already there is accepted, the NDJSON is imported."""
    patterns = {"one": "one*", "two": "two*"}
    answers = [response(200), response(200), response(409), response(200, {"success": True, "successCount": 15})]
    with mock.patch.object(dashboards.requests, "post", side_effect=answers) as post:
        assert install_objects(URL, meta_fields=["_source", "_id"], index_patterns=patterns) == 15
    settings, *registered, imported = post.call_args_list
    assert settings.args == (f"{URL}/api/opensearch-dashboards/settings",)
    assert settings.kwargs["json"] == {"changes": {"metaFields": ["_source", "_id"]}}
    assert [call.args[0] for call in registered] == [
        f"{URL}/api/saved_objects/index-pattern/{name}" for name in patterns
    ]
    assert imported.args == (f"{URL}/api/saved_objects/_import",)
    assert imported.kwargs["params"] == {"overwrite": "true"}


def test_install_objects_only_imports_by_default():
    """Without meta fields or index patterns, only the NDJSON is imported."""
    with mock.patch.object(
        dashboards.requests, "post", return_value=response(200, {"success": True, "successCount": 15})
    ) as post:
        assert install_objects(URL) == 15
    assert post.call_count == 1


def test_install_objects_partly_imported():
    """An import that leaves objects out is an error, though Dashboards answers 200."""
    answer = response(200, {"success": False, "successCount": 14, "errors": [{"id": "search-health"}]})
    with (
        mock.patch.object(dashboards.requests, "post", return_value=answer),
        pytest.raises(dashboards.DashboardsError, match="search-health"),
    ):
        install_objects(URL)


def test_install_objects_refused():
    """A refused index pattern stops the install before the import."""
    with (
        mock.patch.object(dashboards.requests, "post", side_effect=[response(200), response(400)]) as post,
        pytest.raises(requests.HTTPError),
    ):
        install_objects(URL, meta_fields=["_id"], index_patterns={"one": "one*"})
    assert post.call_count == 2


def test_export_dashboard(tmp_path):
    """The export keeps the objects and drops the closing count."""
    lines = [{"type": "index-pattern", "id": "search-monitor"}, {"type": "dashboard", "id": "search-health"}]
    text = "\n".join(json.dumps(line) for line in [*lines, {"exportedCount": 2, "missingRefCount": 0}])
    path = tmp_path / "search-monitor.ndjson"
    with mock.patch.object(dashboards.requests, "post", return_value=response(200, text=text)) as post:
        assert export_dashboard(URL, path=path) == 2
    assert post.call_args.kwargs["json"]["objects"] == [{"type": "dashboard", "id": "search-health"}]
    assert [json.loads(line) for line in path.read_text().splitlines()] == lines


def test_dashboards_cli(app):
    """The command installs the dashboard, skips an unreachable Dashboards on request, and fails otherwise."""
    cli_module = "rero_invenio_base.cli.monitoring"
    with (
        mock.patch(f"{cli_module}.wait_for_dashboards", return_value=True),
        mock.patch(f"{cli_module}.install_objects", return_value=15),
    ):
        res = CliRunner().invoke(dashboards_cli, ["-u", URL])
    assert res.exit_code == 0, res.output
    assert f"15 objects imported: {URL}/app/dashboards#/view/search-health" in res.output
    with mock.patch(f"{cli_module}.dashboards_running", return_value=False):
        res = CliRunner().invoke(dashboards_cli, ["-u", URL, "--skip-unreachable"])
    assert res.exit_code == 0
    assert "skipping" in res.output
    with mock.patch(f"{cli_module}.wait_for_dashboards", return_value=False):
        res = CliRunner().invoke(dashboards_cli, ["-u", URL])
    assert res.exit_code == 1
    assert "not reachable" in res.output


def test_export_dashboard_missing_references(tmp_path):
    """An export missing references leaves the bundle as it is."""
    text = "\n".join(
        json.dumps(line)
        for line in [
            {"type": "dashboard", "id": "search-health"},
            {"exportedCount": 1, "missingRefCount": 1, "missingReferences": [{"id": "gone"}]},
        ]
    )
    path = tmp_path / "search-monitor.ndjson"
    path.write_text("complete bundle")
    with (
        mock.patch.object(dashboards.requests, "post", return_value=response(200, text=text)),
        pytest.raises(dashboards.DashboardsError, match="gone"),
    ):
        export_dashboard(URL, path=path)
    assert path.read_text() == "complete bundle"
