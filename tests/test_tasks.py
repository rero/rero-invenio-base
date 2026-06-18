# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Tests celery tasks."""

import pytest

from rero_invenio_base.modules.tasks import run_on_worker


def test_tasks(capsys):
    """Test celery tasks."""
    code = 'print("simple")'
    run_on_worker(code)
    capsys.readouterr().out == "simple"
    code = """
def display(msg='foo'):
    print(msg)
    return True
    """
    run_on_worker(code, "display")
    capsys.readouterr().out == "foo"

    run_on_worker(code, "display", msg="named arg")
    capsys.readouterr().out == "name arg"

    run_on_worker(code, "display", "arg")
    capsys.readouterr().out == "arg"

    run_on_worker(code, "display")
    capsys.readouterr().out == "foo"

    run_on_worker(code, "display", msg="named arg")
    capsys.readouterr().out == "name arg"

    run_on_worker(code, "display", "arg")
    capsys.readouterr().out == "arg"

    with pytest.raises(KeyError):
        run_on_worker(code, "foo")

    code = 'print(")'
    with pytest.raises(SyntaxError):
        run_on_worker(code, "display", "arg")
