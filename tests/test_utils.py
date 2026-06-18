# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test utils functions."""

from rero_invenio_base.modules.utils import chunk


def test_utils():
    """Test utils functions."""
    assert list(chunk([1, 2, 3, 4, 5], 2)) == [(1, 2), (3, 4), (5,)]

    assert list(chunk(range(1, 6), 2)) == [(1, 2), (3, 4), (5,)]

    assert list(chunk(range(120), 50)) == [
        tuple(range(50)),
        tuple(range(50, 100)),
        tuple(range(100, 120)),
    ]

    assert list(chunk(list(range(120)), 50)) == [
        tuple(range(50)),
        tuple(range(50, 100)),
        tuple(range(100, 120)),
    ]
