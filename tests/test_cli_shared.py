# RERO Invenio Base
# Copyright (C) 2025 RERO.
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
