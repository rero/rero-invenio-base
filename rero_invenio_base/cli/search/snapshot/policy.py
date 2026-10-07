# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click Search snapshot policy command-line utilities.

OpenSearch schedules recurring snapshots through Snapshot Management (SM)
policies served under ``/_plugins/_sm/policies``.  This replaces the
Elasticsearch Snapshot Lifecycle Management (SLM) API, which OpenSearch does
not implement.

See: https://docs.opensearch.org/latest/api-reference/snapshots/snapshot-management/
"""

import json
import sys

import click
from flask.cli import with_appcontext
from invenio_search import current_search_client
from opensearchpy.exceptions import OpenSearchException

from ...shared import abort_if_false

_POLICIES = "/_plugins/_sm/policies"


def _request(method, path, body=None, params=None):
    """Call the SM API, reporting failures and exiting instead of raising.

    :param method: HTTP method.
    :param path: SM API path.
    :param body: optional request payload.
    :param params: optional query string parameters.
    :returns: the decoded API response.
    """
    try:
        return current_search_client.transport.perform_request(method, path, body=body, params=params)
    except OpenSearchException as err:
        click.secho(f"ERROR: {err}", fg="red")
        sys.exit(1)


def _echo_json(data, fg="green"):
    """Print an API response as indented JSON.

    :param data: decoded API response.
    :param fg: click foreground colour.
    """
    click.secho(json.dumps(data, indent=2), fg=fg)


def _print_policy_table(policies):
    """Render a condensed policy table to the terminal.

    :param policies: list of policy entries as returned by the SM list API.
    """
    header = "POLICY"
    name_width = max([len(header), *[len(p["sm_policy"]["name"]) for p in policies]])
    click.secho(f"  {header:<{name_width}}  {'REPOSITORY':<24}  {'SCHEDULE':<18}  STATE", bold=True)
    for entry in policies:
        sm_policy = entry["sm_policy"]
        repository = sm_policy.get("snapshot_config", {}).get("repository", "?")
        schedule = sm_policy.get("creation", {}).get("schedule", {}).get("cron", {}).get("expression", "?")
        enabled = sm_policy.get("enabled", False)
        click.echo(f"  {sm_policy['name']:<{name_width}}  {repository:<24}  {schedule:<18}  ", nl=False)
        click.secho("ENABLED" if enabled else "DISABLED", fg="green" if enabled else "yellow")


@click.group()
def policy():
    """Search snapshot management (SM) policy commands."""


@policy.command("list")
@with_appcontext
@click.option("-N", "--names-only", is_flag=True, default=False, help="Print only policy names, one per line.")
def list_policy(names_only):
    """List snapshot management policies.

    :param names_only: print bare policy names instead of a table.
    """
    if not (policies := _request("GET", _POLICIES).get("policies")):
        click.secho("No policies found.", fg="yellow")
        return
    if names_only:
        for entry in policies:
            click.echo(entry["sm_policy"]["name"])
    else:
        _print_policy_table(policies)


@policy.command("get")
@with_appcontext
@click.argument("name")
def get_policy(name):
    """Show the full definition of a snapshot management policy.

    :param name: policy name.
    """
    _echo_json(_request("GET", f"{_POLICIES}/{name}"))


@policy.command("explain")
@with_appcontext
@click.argument("name", default="*", required=False)
def explain_policy(name):
    """Explain the current execution state of snapshot management policies.

    NAME accepts a wildcard and defaults to ``*`` (all policies).  This is the
    OpenSearch counterpart to the Elasticsearch SLM status API.

    :param name: policy name or pattern.
    """
    _echo_json(_request("GET", f"{_POLICIES}/{name}/_explain"))


@policy.command("create")
@with_appcontext
@click.argument("name")
@click.argument("body_file", type=click.File("r"))
def create_policy(name, body_file):
    """Create a snapshot management policy from a JSON definition file.

    BODY_FILE must contain at least a ``creation`` schedule and a
    ``snapshot_config`` naming the target repository.  Note that OpenSearch
    does not verify that the repository exists.

    :param name: policy name.
    :param body_file: JSON file containing the policy definition.
    """
    _echo_json(_request("POST", f"{_POLICIES}/{name}", body=json.load(body_file)))


@policy.command("update")
@with_appcontext
@click.argument("name")
@click.argument("body_file", type=click.File("r"))
def update_policy(name, body_file):
    """Update an existing snapshot management policy.

    The SM API requires the current sequence number and primary term on
    update, so they are read back from the policy before it is replaced.

    :param name: policy name.
    :param body_file: JSON file containing the new policy definition.
    """
    current = _request("GET", f"{_POLICIES}/{name}")
    params = {"if_seq_no": current["_seq_no"], "if_primary_term": current["_primary_term"]}
    _echo_json(_request("PUT", f"{_POLICIES}/{name}", body=json.load(body_file), params=params))


@policy.command("start")
@with_appcontext
@click.argument("name")
def start_policy(name):
    """Enable a snapshot management policy.

    :param name: policy name.
    """
    _echo_json(_request("POST", f"{_POLICIES}/{name}/_start"))


@policy.command("stop")
@with_appcontext
@click.argument("name")
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to stop the policy?",
)
def stop_policy(name):
    """Disable a snapshot management policy, stopping scheduled snapshots.

    :param name: policy name.
    """
    _echo_json(_request("POST", f"{_POLICIES}/{name}/_stop"), fg="yellow")


@policy.command("delete")
@with_appcontext
@click.argument("name")
@click.option(
    "--yes-i-know",
    is_flag=True,
    callback=abort_if_false,
    expose_value=False,
    prompt="Do you really want to delete the policy?",
)
def delete_policy(name):
    """Delete a snapshot management policy.

    Snapshots already created by the policy are kept.

    :param name: policy name.
    """
    _echo_json(_request("DELETE", f"{_POLICIES}/{name}"), fg="red")
