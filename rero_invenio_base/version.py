# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Version information for RERO Invenio Base.

This file is imported by ``rero_invenio_base.__init__``,
and parsed by ``setup.py``.
"""

from importlib import metadata

__version__ = metadata.version(__package__)
