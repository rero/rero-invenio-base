# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Version information for RERO Invenio Base, read from the installed package metadata."""

from importlib import metadata

__version__ = metadata.version("rero-invenio-base")
