# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test the batch command."""

import click
import pytest
from click.testing import CliRunner
from flask.cli import FlaskGroup, ScriptInfo

from rero_invenio_base.cli.batch import batch, read_commands


def invoke_batch(app, tmp_path, content, options=None):
    """Run a batch file through a root group carrying two probe commands.

    ``batch`` resolves each line against the root group, so it has to be invoked
    through a ``FlaskGroup`` and not on its own: that is what makes the commands
    of an instance reachable, and what keeps the file format identical to the one
    a setup script feeds it. It is added to the group here the way an instance
    adds it to its own, rather than reached through the ``flask.commands`` entry
    point, which is inactive while the package is not installed. The probes stand
    in for the commands of the instance, so that these tests depend on none.

    :param app: the Flask application to reuse, never rebuilt.
    :param tmp_path: pytest temporary directory.
    :param content: the batch file content.
    :param options: extra options for the batch command.
    :returns: the click result.
    """
    cli = FlaskGroup(create_app=lambda: app)
    cli.add_command(batch)

    @cli.command("probe")
    @click.argument("marker")
    def probe(marker):
        """Echo its argument, standing in for a command of the instance."""
        click.echo(f"probe {marker}")

    @cli.command("explode")
    def explode():
        """Fail, standing in for a command of the instance that raises."""
        raise RuntimeError("boom")

    infile = tmp_path / "commands.batch"
    infile.write_text(content)
    args = ["batch", *(options or []), str(infile)]
    return CliRunner().invoke(cli, args, obj=ScriptInfo(create_app=lambda: app))


def test_read_commands(tmp_path):
    """Test that blank lines and comments are skipped."""
    infile = tmp_path / "commands.batch"
    infile.write_text("# a comment\n\n  probe 'a marker'\n\n# another\nprobe second\n")
    with infile.open() as opened:
        assert read_commands(opened) == [
            (3, ["probe", "a marker"]),
            (6, ["probe", "second"]),
        ]


def test_read_commands_names_the_unparsable_line(tmp_path):
    """Test that unbalanced quotes are reported, and not raised raw."""
    infile = tmp_path / "commands.batch"
    infile.write_text("probe first\nprobe 'unclosed\n")
    with infile.open() as opened, pytest.raises(click.ClickException, match="line 2"):
        read_commands(opened)


def test_batch_refuses_an_unparsable_file(app, tmp_path):
    """Test that nothing runs when a line cannot be parsed.

    The file is read whole before the first command, so the batch stops before
    doing anything rather than halfway through.
    """
    res = invoke_batch(app, tmp_path, "probe first\nprobe 'unclosed\n")
    assert res.exit_code != 0
    assert "cannot parse line 2: No closing quotation" in res.output
    assert "probe first" not in res.output


def test_batch_runs_every_line(app, tmp_path):
    """Test that several commands run in a single application process."""
    res = invoke_batch(app, tmp_path, "# a comment\n\nprobe first\nprobe second\n")
    assert res.exit_code == 0
    assert "probe first" in res.output
    assert "probe second" in res.output
    assert "[batch:3]" in res.output
    assert "[batch:4]" in res.output


def test_batch_stops_on_error(app, tmp_path):
    """Test that the batch stops at the first failing command."""
    res = invoke_batch(app, tmp_path, "probe first\nexplode\nprobe third\n")
    assert res.exit_code != 0
    assert "probe first" in res.output
    assert "[batch:2] failed: boom" in res.output
    # the third line is never even announced, so it never started
    assert "[batch:3]" not in res.output
    assert "batch failed on line(s): 2" in res.output


def test_batch_continue_on_error(app, tmp_path):
    """Test that --continue-on-error runs the remaining commands."""
    res = invoke_batch(app, tmp_path, "explode\nprobe second\n", options=["--continue-on-error"])
    assert res.exit_code != 0
    assert "[batch:1] failed: boom" in res.output
    # the second line ran despite the failure, which is the point of the option
    assert "probe second" in res.output
    assert "batch failed on line(s): 1" in res.output


def test_batch_reports_the_reset_cost(app, tmp_path):
    """Test that the reset cost is reported apart from the command time."""
    res = invoke_batch(app, tmp_path, "probe first\n", options=["-t"])
    assert res.exit_code == 0
    assert "s reset" in res.output
    assert "[batch] reset total:" in res.output


def test_batch_without_refresh(app, tmp_path):
    """Test that --no-refresh still commits and still reports the reset."""
    res = invoke_batch(app, tmp_path, "probe first\nprobe second\n", options=["-t", "--no-refresh"])
    assert res.exit_code == 0
    assert "probe second" in res.output
    assert "[batch] reset total:" in res.output
