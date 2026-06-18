# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""RERO Invenio base module declaration for streamed exports."""


class ReroInvenioBaseExportApp:
    """RERO Invenio base export app."""

    def __init__(self, app=None):
        """Extension initialization."""
        if app:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        """Flask application initialization."""
        self.init_config(app)
        app.extensions["rero_invenio_base_exports"] = self

    def init_config(self, app):
        """Initialize configuration."""
        for k in dir(app.config):
            if k.startswith("RERO_INVENIO_BASE_EXPORT"):
                app.config.setdefault(k, getattr(app.config, k))
