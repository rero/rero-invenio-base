# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test shared CLI functions."""

from unittest.mock import MagicMock

from rero_invenio_base.cli.shared import abort_if_false


def test_abort_if_false_with_true():
    """Test abort_if_false with True value."""
    ctx = MagicMock()
    abort_if_false(ctx, None, True)
    ctx.abort.assert_not_called()


def test_abort_if_false_with_false():
    """Test abort_if_false with False value."""
    ctx = MagicMock()
    abort_if_false(ctx, None, False)
    ctx.abort.assert_called_once()
