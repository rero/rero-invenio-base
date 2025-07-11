# RERO Invenio Base
# Copyright (C) 2023 RERO.
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
