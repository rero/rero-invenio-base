# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""RERO Invenio base module declaration for streamed exports."""

from . import config


class ReroInvenioBaseExportApp:
    """RERO Invenio base export app."""

    def __init__(self, app=None):
        """Initialize the RERO Invenio base export extension.

        :param app: Flask application instance (optional)
        """
        if app:
            self.app = app
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Flask application with this extension.

        Registers the extension and initializes configuration.

        :param app: Flask application instance
        """
        self.init_config(app)
        app.extensions["rero_invenio_base_exports"] = self

    def init_config(self, app):
        """Initialize configuration defaults for the export module.

        Sets default values for all RERO_INVENIO_BASE_EXPORT configuration keys.

        :param app: Flask application instance
        """
        for k in dir(config):
            if k.startswith("RERO_INVENIO_BASE_EXPORT"):
                app.config.setdefault(k, getattr(config, k))
