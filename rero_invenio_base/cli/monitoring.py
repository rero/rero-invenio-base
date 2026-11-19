# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click monitoring command-line utilities."""

import click
import requests
from flask import current_app
from flask.cli import with_appcontext

from ..modules.monitoring.api import (
    Monitoring,
    db_connection_counts,
    db_connections,
    get_timestamps,
    redis_info,
    search_health,
    search_indices,
)
from ..modules.monitoring.dashboards import (
    SEARCH_MONITOR_DASHBOARD_ID,
    dashboards_running,
    export_dashboard,
    install_objects,
    wait_for_dashboards,
)


@click.group()
def monitoring():
    """Monitor the database, the search engine, Redis and the scheduled tasks."""


def _print_missing(monitoring_api, doc_type):
    try:
        missing = monitoring_api.missing(doc_type)
    except KeyError:
        raise click.ClickException(f"Document type not found: {doc_type}") from None
    for key in ("DB", "search", "search duplicate"):
        if pids := missing[key]:
            click.secho(f"{doc_type} missing in {key}: {', '.join(pids)}", fg="red")


@monitoring.command("search-db-counts")
@click.option("-m", "--missing", is_flag=True, default=False, help="Display the missing pids.")
@click.option("-d", "--delay", default=1, show_default=True, help="Recent minutes to ignore.")
@with_appcontext
def search_db_counts(missing, delay):
    """Print the database and index counts of each record type."""
    monitoring_api = Monitoring(time_delta=delay)
    info = monitoring_api.info()
    click.echo(f"{'DB - search':>11} {'type':>8} {'count':>10} {'index':>25} {'count':>10}")
    click.echo("-" * 68)
    for doc_type, data in sorted(info.items()):
        line = f"{data['db-search']:>11} {doc_type:>8} {data['db']:>10} {data['index']:>25} {data['search']:>10}"
        click.secho(line, fg="red" if data["db-search"] else None)
    if missing:
        for doc_type, data in sorted(info.items()):
            if data["db-search"]:
                _print_missing(monitoring_api, doc_type)


@monitoring.command("search-db-missing")
@click.argument("doc_type")
@click.option("-d", "--delay", default=1, show_default=True, help="Recent minutes to ignore.")
@with_appcontext
def search_db_missing(doc_type, delay):
    """Print the pids of DOC_TYPE missing in the database or in the index."""
    _print_missing(Monitoring(time_delta=delay), doc_type)


@monitoring.command()
@with_appcontext
def timestamps():
    """Print the recorded events of the scheduled tasks."""
    for name, event in get_timestamps().items():
        details = " | ".join(f"{key}={value}" for key, value in event.items() if key not in ("utctime", "unixtime"))
        click.echo(f"{event['utctime']}: {name} {details}")


@monitoring.command("search")
@with_appcontext
def search_health_cli():
    """Print the health of the search cluster."""
    for key, value in search_health().items():
        click.echo(f"{key:<33}: {value}")


@monitoring.command("search-indices")
@with_appcontext
def search_indices_cli():
    """Print the search indices."""
    for name, row in search_indices().items():
        click.echo(
            f"{row['health']:<7} {row['status']:<6} {name:<55} {row['docs.count'] or '-':>10} {row['store.size'] or '-':>14}"
        )


@monitoring.command()
@with_appcontext
def redis():
    """Print the information of each Redis instance."""
    for name, info in redis_info().items():
        click.secho(f"[{name}]", fg="green")
        for key, value in info.items():
            click.echo(f"  {key:<33}: {value}")


@monitoring.command("db-connection-counts")
@with_appcontext
def db_connection_counts_cli():
    """Print the PostgreSQL connection counts."""
    click.echo(", ".join(f"{key}: {value}" for key, value in db_connection_counts().items()))


@monitoring.command("db-connections")
@with_appcontext
def db_connections_cli():
    """Print the PostgreSQL connections."""
    for pid, connection in db_connections().items():
        click.echo(f"pid: {pid}")
        for key, value in connection.items():
            click.echo(f"  {key:<16}: {value}")


@monitoring.command()
@click.option("-u", "--url", default=None, help="Dashboards URL, else RERO_INVENIO_BASE_MONITORING_DASHBOARDS_URL.")
@click.option("-e", "--export", is_flag=True, default=False, help="Write the dashboard as edited back to the NDJSON.")
@click.option("-s", "--skip-unreachable", is_flag=True, default=False, help="Exit without error when unreachable.")
@with_appcontext
def dashboards(url, export, skip_unreachable):
    """Install the search health dashboard into the search dashboards, or export it from there."""
    url = (url or current_app.config["RERO_INVENIO_BASE_MONITORING_DASHBOARDS_URL"]).rstrip("/")
    if skip_unreachable and not dashboards_running(url):
        click.secho(f"No search dashboards at {url}: skipping the search health dashboard", fg="yellow")
        return
    if not wait_for_dashboards(url):
        raise click.ClickException(f"Search dashboards not reachable at {url}")
    try:
        if export:
            click.secho(f"{export_dashboard(url)} objects exported from {url}", fg="green")
        else:
            count = install_objects(url)
            click.secho(
                f"{count} objects imported: {url}/app/dashboards#/view/{SEARCH_MONITOR_DASHBOARD_ID}", fg="green"
            )
    except requests.RequestException as error:
        raise click.ClickException(f"Search dashboards at {url}: {error}") from error
