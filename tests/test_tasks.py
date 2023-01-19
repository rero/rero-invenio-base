# -*- coding: utf-8 -*-
#
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

"""Tests celery tasks."""

import pytest

from rero_invenio_base.modules.tasks import run_on_worker


def test_tasks(capsys):
    """Test celery tasks."""
    code = 'print("simple")'
    run_on_worker(code)
    capsys.readouterr().out == 'simple'
    code = """
def display(msg='foo'):
    print(msg)
    return True
    """
    run_on_worker(code, 'display')
    capsys.readouterr().out == 'foo'

    run_on_worker(code, 'display', msg='named arg')
    capsys.readouterr().out == 'name arg'

    run_on_worker(code, 'display', 'arg')
    capsys.readouterr().out == 'arg'

    run_on_worker(code, 'display')
    capsys.readouterr().out == 'foo'

    run_on_worker(code, 'display', msg='named arg')
    capsys.readouterr().out == 'name arg'

    run_on_worker(code, 'display', 'arg')
    capsys.readouterr().out == 'arg'

    with pytest.raises(KeyError):
        run_on_worker(code, 'foo')

    code = 'print(")'
    with pytest.raises(SyntaxError):
        run_on_worker(code, 'display', 'arg')
