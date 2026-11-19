# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""REST API of the monitoring, read by Zabbix."""

from flask import Blueprint, current_app, jsonify, request, url_for
from flask_login import current_user
from flask_principal import RoleNeed
from invenio_access import Permission
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.routing import BuildError

from .api import (
    Monitoring,
    db_connection_counts,
    db_connections,
    get_timestamps,
    harvests,
    queues,
    redis_info,
    search_health,
    search_indices,
    snapshots,
)

blueprint = Blueprint("api_monitoring", __name__, url_prefix="/monitoring")


def _flag(name):
    """Tell whether a query argument is set to true."""
    return request.args.get(name, "").lower() in ("1", "true", "yes")


def _error(code, title, details, status):
    return jsonify({"error": {"id": code, "code": code, "title": title, "details": details}}), status


@blueprint.before_request
def check_permission():
    """Let only the monitoring role and the superusers in."""
    if not current_user.is_authenticated:
        return jsonify({"status": "error: Unauthorized"}), 401
    if not Permission(RoleNeed(current_app.config["RERO_INVENIO_BASE_MONITORING_ROLE"])).can():
        return jsonify({"status": "error: Forbidden"}), 403
    return None


@blueprint.errorhandler(SQLAlchemyError)
def database_error(error):
    """Answer a database error with a 500."""
    current_app.logger.error(f"Monitoring database error: {error}")
    return _error("DATABASE_ERROR", "Database error.", str(error), 500)


@blueprint.route("/db_connection_counts")
def db_connection_counts_view():
    """Display the PostgreSQL connection counts."""
    return jsonify({"data": db_connection_counts()})


@blueprint.route("/db_connections")
def db_connections_view():
    """Display the PostgreSQL connections."""
    return jsonify({"data": db_connections()})


@blueprint.route("/search_db_counts")
def search_db_counts():
    """Display the database and index counts of each record type.

    Query arguments: `deleted` counts the deleted records too, `diff` lists the
    differing pids of the types whose counts are equal, `delay` is the number of
    recent minutes to ignore.
    """
    monitoring = Monitoring(time_delta=request.args.get("delay", 1))
    return jsonify({"data": monitoring.info(_flag("deleted"), _flag("diff"))})


@blueprint.route("/check_search_db_counts")
def check_search_db_counts():
    """Display green when the database and the index agree, else red with the errors."""
    monitoring = Monitoring(time_delta=request.args.get("delay", 1))
    checks = monitoring.check(_flag("deleted"), _flag("diff"))
    if not checks:
        return jsonify({"data": {"status": "green"}})
    errors = []
    messages = {
        "db-search": ("DB_SEARCH_COUNTER_MISMATCH", "DB items counts don't match search items count.", "search"),
        "db-": ("DB_SEARCH_UNEQUAL", "DB items unequal search items.", "DB"),
        "search-": ("DB_SEARCH_UNEQUAL", "DB items unequal search items.", "search"),
    }
    for doc_type, check in checks.items():
        links = {
            "about": url_for("api_monitoring.check_search_db_counts", _external=True),
            doc_type: url_for("api_monitoring.missing_pids", doc_type=doc_type, _external=True),
        }
        for key, count in check.items():
            code, title, missing_in = messages[key]
            if key == "db-search" and count < 0:
                missing_in = "DB"
            errors.append(
                {
                    "id": code,
                    "code": code,
                    "title": title,
                    "details": f"There are {abs(count)} items from {doc_type} missing in {missing_in}.",
                    "links": links,
                }
            )
    return jsonify({"data": {"status": "red"}, "errors": errors})


@blueprint.route("/missing_pids/<doc_type>")
def missing_pids(doc_type):
    """List the pids of a record type missing in the database or in the index.

    The pids are given as record URLs when the record type has a REST endpoint.
    """
    monitoring = Monitoring(time_delta=request.args.get("delay", 1))
    try:
        missing = monitoring.missing(doc_type, _flag("deleted"))
    except KeyError:
        return _error(
            "DOCUMENT_TYPE_NOT_FOUND", "Document type not found.", f"Document type not found: {doc_type}", 404
        )
    try:
        api_url = url_for(f"invenio_records_rest.{doc_type}_list", _external=True)
    except BuildError:
        return jsonify({"data": missing})
    return jsonify(
        {
            "data": {
                "DB": [f'{api_url}?q=pid:"{pid}"' for pid in missing["DB"]],
                "search": [f"{api_url}{pid}" for pid in missing["search"]],
                "search duplicate": [f'{api_url}?q=pid:"{pid}"' for pid in missing["search duplicate"]],
            }
        }
    )


@blueprint.route("/redis")
def redis():
    """Display the information of each Redis instance."""
    return jsonify({"data": redis_info()})


@blueprint.route("/search")
def search_health_view():
    """Display the health of the search cluster."""
    return jsonify({"data": search_health()})


@blueprint.route("/search_indices")
def search_indices_view():
    """Display the search indices."""
    return jsonify({"data": search_indices()})


@blueprint.route("/timestamps")
def timestamps():
    """Display the recorded events of the scheduled tasks."""
    return jsonify({"data": get_timestamps()})


@blueprint.route("/snapshots")
def snapshots_view():
    """Display the last snapshots of each repository and the snapshot policies."""
    return jsonify({"data": snapshots()})


@blueprint.route("/queues")
def queues_view():
    """Display the messages and consumers of the queues."""
    return jsonify({"data": queues()})


@blueprint.route("/harvests")
def harvests_view():
    """Display the last run of each OAI harvest source."""
    return jsonify({"data": harvests()})
