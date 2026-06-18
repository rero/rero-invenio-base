# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Module tests."""

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
