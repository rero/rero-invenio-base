# -*- coding: utf-8 -*-
#
# RERO Invenio Base
# Copyright (C) 2022 RERO.
# Copyright (C) 2022 UCLouvain.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.


"""Extension initialization tests."""

from __future__ import absolute_import, print_function

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
    app.config["RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS"] = dict(
        record=dict(
            resource=rest_endpoints["recid"],
            default_media_type="text/csv",
            search_serializers={
                "text/csv": "invenio_records_rest.serializers:json_v1_response",
            },
            search_serializers_aliases={"csv": "text/csv"},
        )
    )
    blueprint = create_blueprint_from_app(app)
    app.register_blueprint(blueprint)

    routes = [str(p) for p in app.url_map.iter_rules()]
    route_to_test = f"/export{rest_endpoints['recid']['list_route']}"
    assert route_to_test in routes
