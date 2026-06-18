# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later


"""Extension initialization tests."""

from flask import Flask

from rero_invenio_base.modules.export.ext import ReroInvenioBaseExportApp
from rero_invenio_base.modules.export.views import create_blueprint_from_app


def test_init():
    """Test extension initialization."""
    app = Flask("testapp")
    ext = ReroInvenioBaseExportApp()
    assert "rero_invenio_base_exports" not in app.extensions
    ext.init_app(app)
    assert "rero_invenio_base_exports" in app.extensions


def test_blueprints(app):
    """Test blueprints."""
    rest_endpoints = app.config.get("RECORDS_REST_ENDPOINTS")
    app.config["RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS"] = {
        "record": {
            "resource": rest_endpoints["recid"],
            "default_media_type": "text/csv",
            "search_serializers": {
                "text/csv": "invenio_records_rest.serializers:json_v1_response",
            },
            "search_serializers_aliases": {"csv": "text/csv"},
        }
    }
    blueprint = create_blueprint_from_app(app)
    app.register_blueprint(blueprint)

    routes = [str(p) for p in app.url_map.iter_rules()]
    route_to_test = f"/export{rest_endpoints['recid']['list_route']}"
    assert route_to_test in routes
