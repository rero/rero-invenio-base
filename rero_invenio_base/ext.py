# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic backend libraries for RERO Invenio instances."""

from . import config


class REROInvenioBase:
    """RERO Invenio Base extension."""

    def __init__(self, app=None):
        """Initialize the RERO Invenio base extension.

        :param app: Flask application instance (optional)
        """
        if app:
            self.init_app(app)

    def init_app(self, app):
        """Initialize the Flask application with this extension.

        Registers the extension and initializes configuration.

        :param app: Flask application instance
        """
        self.init_config(app)
        app.extensions["rero-invenio-base"] = self

    def init_config(self, app):
        """Initialize configuration defaults.

        Sets default values for all RERO_INVENIO_BASE configuration keys.

        :param app: Flask application instance
        """
        # Use theme's base template if theme is installed
        if "BASE_TEMPLATE" in app.config:
            app.config.setdefault(
                "RERO_INVENIO_BASE_BASE_TEMPLATE",
                app.config["BASE_TEMPLATE"],
            )
        for k in dir(config):
            if k.startswith("RERO_INVENIO_BASE_"):
                app.config.setdefault(k, getattr(config, k))
