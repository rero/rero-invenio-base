# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli search snapshot policy commands."""

import json
from unittest.mock import MagicMock, patch

import pytest
from opensearchpy.exceptions import NotFoundError

from rero_invenio_base.cli.search.snapshot.policy import (
    create_policy,
    delete_policy,
    explain_policy,
    get_policy,
    list_policy,
    start_policy,
    stop_policy,
    update_policy,
)

POLICY_BODY = {
    "description": "daily snapshots",
    "creation": {"schedule": {"cron": {"expression": "0 2 * * *", "timezone": "UTC"}}},
    "snapshot_config": {"repository": "my-repo", "indices": "*"},
}


def _policy_entry(name="daily", repository="my-repo", enabled=True):
    """Build a policy list entry as returned by the SM API."""
    return {
        "_id": f"{name}-sm-policy",
        "_seq_no": 7,
        "_primary_term": 1,
        "sm_policy": {
            "name": name,
            "creation": {"schedule": {"cron": {"expression": "0 2 * * *"}}},
            "snapshot_config": {"repository": repository},
            "enabled": enabled,
        },
    }


@pytest.fixture
def sm_request():
    """Patch the SM transport layer and yield the request mock."""
    with patch("rero_invenio_base.cli.search.snapshot.policy.current_search_client") as mock_client:
        mock_client.transport.perform_request = MagicMock(return_value={})
        yield mock_client.transport.perform_request


@pytest.fixture
def policy_file(tmp_path):
    """Write a policy definition to a temporary JSON file."""
    path = tmp_path / "policy.json"
    path.write_text(json.dumps(POLICY_BODY))
    return str(path)


def test_list_policy_table(app, es_runner, sm_request):
    """List renders a table of policies."""
    sm_request.return_value = {"policies": [_policy_entry(), _policy_entry("weekly", "other-repo", enabled=False)]}
    res = es_runner.invoke(list_policy, [], obj=app)
    assert res.exit_code == 0
    assert "daily" in res.output
    assert "my-repo" in res.output
    assert "ENABLED" in res.output
    assert "DISABLED" in res.output
    sm_request.assert_called_once_with("GET", "/_plugins/_sm/policies", body=None, params=None)


def test_list_policy_names_only(app, es_runner, sm_request):
    """List with --names-only prints bare names."""
    sm_request.return_value = {"policies": [_policy_entry(), _policy_entry("weekly")]}
    res = es_runner.invoke(list_policy, ["--names-only"], obj=app)
    assert res.exit_code == 0
    assert res.output.split() == ["daily", "weekly"]


def test_list_policy_empty(app, es_runner, sm_request):
    """List reports when no policy is defined."""
    sm_request.return_value = {"policies": [], "total_policies": 0}
    res = es_runner.invoke(list_policy, [], obj=app)
    assert res.exit_code == 0
    assert "No policies found." in res.output


def test_get_policy(app, es_runner, sm_request):
    """Get prints the full policy definition."""
    sm_request.return_value = _policy_entry()
    res = es_runner.invoke(get_policy, ["daily"], obj=app)
    assert res.exit_code == 0
    assert "daily-sm-policy" in res.output
    sm_request.assert_called_once_with("GET", "/_plugins/_sm/policies/daily", body=None, params=None)


def test_explain_policy_defaults_to_wildcard(app, es_runner, sm_request):
    """Explain targets all policies when no name is given."""
    sm_request.return_value = {"policies": [{"name": "daily", "enabled": True}]}
    res = es_runner.invoke(explain_policy, [], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("GET", "/_plugins/_sm/policies/*/_explain", body=None, params=None)


def test_explain_policy_by_name(app, es_runner, sm_request):
    """Explain targets a single policy when named."""
    sm_request.return_value = {"policies": [{"name": "daily", "enabled": True}]}
    res = es_runner.invoke(explain_policy, ["daily"], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("GET", "/_plugins/_sm/policies/daily/_explain", body=None, params=None)


def test_create_policy_uses_post(app, es_runner, sm_request, policy_file):
    """Create sends the definition with POST, as required by the SM API."""
    sm_request.return_value = {"_id": "daily-sm-policy", "_version": 1}
    res = es_runner.invoke(create_policy, ["daily", policy_file], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("POST", "/_plugins/_sm/policies/daily", body=POLICY_BODY, params=None)


def test_update_policy_sends_seq_no(app, es_runner, sm_request, policy_file):
    """Update reads back the sequence number and primary term before writing."""
    sm_request.side_effect = [_policy_entry(), {"_version": 2}]
    res = es_runner.invoke(update_policy, ["daily", policy_file], obj=app)
    assert res.exit_code == 0
    assert sm_request.call_args_list[0].args == ("GET", "/_plugins/_sm/policies/daily")
    assert sm_request.call_args_list[1] == (
        ("PUT", "/_plugins/_sm/policies/daily"),
        {"body": POLICY_BODY, "params": {"if_seq_no": 7, "if_primary_term": 1}},
    )


def test_start_policy(app, es_runner, sm_request):
    """Start enables the policy."""
    sm_request.return_value = {"acknowledged": True}
    res = es_runner.invoke(start_policy, ["daily"], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("POST", "/_plugins/_sm/policies/daily/_start", body=None, params=None)


def test_stop_policy(app, es_runner, sm_request):
    """Stop disables the policy once confirmed."""
    sm_request.return_value = {"acknowledged": True}
    res = es_runner.invoke(stop_policy, ["daily", "--yes-i-know"], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("POST", "/_plugins/_sm/policies/daily/_stop", body=None, params=None)


def test_stop_policy_aborts_without_confirmation(app, es_runner, sm_request):
    """Stop aborts when the confirmation prompt is declined."""
    res = es_runner.invoke(stop_policy, ["daily"], input="n\n", obj=app)
    assert res.exit_code == 1
    sm_request.assert_not_called()


def test_delete_policy(app, es_runner, sm_request):
    """Delete removes the policy once confirmed."""
    sm_request.return_value = {"result": "deleted"}
    res = es_runner.invoke(delete_policy, ["daily", "--yes-i-know"], obj=app)
    assert res.exit_code == 0
    sm_request.assert_called_once_with("DELETE", "/_plugins/_sm/policies/daily", body=None, params=None)


def test_delete_policy_aborts_without_confirmation(app, es_runner, sm_request):
    """Delete aborts when the confirmation prompt is declined."""
    res = es_runner.invoke(delete_policy, ["daily"], input="n\n", obj=app)
    assert res.exit_code == 1
    sm_request.assert_not_called()


def test_policy_error_exits_1(app, es_runner, sm_request):
    """A failing SM call reports the error and exits 1."""
    sm_request.side_effect = NotFoundError(404, "policy_missing", "no such policy")
    res = es_runner.invoke(get_policy, ["missing"], obj=app)
    assert res.exit_code == 1
    assert "ERROR:" in res.output
