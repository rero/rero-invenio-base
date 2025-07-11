# RERO Invenio Base
# Copyright (C) 2022 RERO.
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
