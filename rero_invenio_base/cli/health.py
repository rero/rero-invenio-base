# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click health-check command-line utility."""

from urllib.parse import urlparse, urlunparse

import click
from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db
from invenio_search import current_search_client
from sqlalchemy import text


@click.command("health")
@with_appcontext
def health():
    """Check connectivity to SEARCH, database, and Redis.

    Exits with status 1 if any service is unreachable or in error state.
    """
    all_ok = True

    # SEARCH
    try:
        s = current_search_client.cluster.health()
        color = {"green": "green", "yellow": "yellow"}.get(s["status"], "red")
        label = "OK" if s["status"] != "red" else "ERROR"
        detail = f"{s['status'].upper()} — {s['number_of_nodes']} node(s), cluster: {s['cluster_name']}"
        click.secho(f"{'SEARCH':<12} {label:<7} {detail}", fg=color)
        if s["status"] == "red":
            all_ok = False
    except Exception as err:
        click.secho(f"{'SEARCH':<12} {'ERROR':<7} {err}", fg="red")
        all_ok = False

    # Database
    try:
        db.session.execute(text("SELECT 1"))
        click.secho(f"{'Database':<12} {'OK':<7}", fg="green")
    except Exception as err:
        click.secho(f"{'Database':<12} {'ERROR':<7} {err}", fg="red")
        all_ok = False

    # Broker / Redis — use Celery's own connection so any broker type works.
    try:
        from celery import current_app as celery_app

        with celery_app.connection() as conn:
            conn.ensure_connection(max_retries=1)
        broker_url = current_app.config.get("BROKER_URL") or current_app.config.get("CELERY_BROKER_URL", "")
        parsed = urlparse(broker_url)
        host = parsed.hostname or ""
        netloc = f"{host}:{parsed.port}" if parsed.port else host
        safe_url = urlunparse(parsed._replace(netloc=netloc))
        click.secho(f"{'Broker':<12} {'OK':<7} {safe_url[:60]}", fg="green")
    except Exception as err:
        click.secho(f"{'Broker':<12} {'ERROR':<7} {err}", fg="red")
        all_ok = False

    if not all_ok:
        raise SystemExit(1)
