# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Generic backend libraries for RERO Invenio instances."""

from .ext import REROInvenioBase
from .version import __version__

__all__ = ("REROInvenioBase", "__version__")
