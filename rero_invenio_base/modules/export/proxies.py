# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Helper proxy."""

from flask import current_app
from werkzeug.local import LocalProxy

current_export = LocalProxy(lambda: current_app.extensions["rero_invenio_base_exports"])
"""Helper proxy to get the current 'RERO Invenio base' exports extension."""
