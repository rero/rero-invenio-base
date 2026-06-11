# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests celery tasks."""

import pytest

from rero_invenio_base.modules.tasks import run_on_worker


def test_tasks(capsys):
    """Test celery tasks."""
    code = 'print("simple")'
    run_on_worker(code)
    assert capsys.readouterr().out == "simple\n"
    code = """
def display(msg='foo'):
    print(msg)
    return True
    """
    run_on_worker(code, "display")
    assert capsys.readouterr().out == "foo\n"

    run_on_worker(code, "display", msg="named arg")
    assert capsys.readouterr().out == "named arg\n"

    run_on_worker(code, "display", "arg")
    assert capsys.readouterr().out == "arg\n"

    with pytest.raises(KeyError):
        run_on_worker(code, "foo")

    code = 'print(")'
    with pytest.raises(SyntaxError):
        run_on_worker(code)
