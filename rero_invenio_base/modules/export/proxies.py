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

"""Helper proxy."""

from flask import current_app
from werkzeug.local import LocalProxy

current_export = LocalProxy(lambda: current_app.extensions["rero_invenio_base_exports"])
"""Helper proxy to get the current 'RERO Invenio base' exports extension."""
