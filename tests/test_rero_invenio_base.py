# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Module tests."""

from importlib.metadata import entry_points

from flask import Flask

from rero_invenio_base import REROInvenioBase


def test_version():
    """Test version import."""
    from rero_invenio_base import __version__

    assert __version__


def test_init():
    """Test extension initialization."""
    app = Flask("testapp")
    ext = REROInvenioBase(app)
    assert "rero-invenio-base" in app.extensions

    app = Flask("testapp")
    ext = REROInvenioBase()
    assert "rero-invenio-base" not in app.extensions
    ext.init_app(app)
    assert "rero-invenio-base" in app.extensions


def test_entry_points():
    """The extension is loaded by the UI and the API applications."""
    for group in ("invenio_base.apps", "invenio_base.api_apps"):
        assert REROInvenioBase in [entry_point.load() for entry_point in entry_points(group=group)]
