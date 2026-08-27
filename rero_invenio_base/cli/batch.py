# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-FileCopyrightText: UCLouvain
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click command-line utilities."""

import shlex
import time

import click
from flask.cli import with_appcontext
from invenio_db import db
from invenio_search.proxies import current_search_client


def read_commands(infile):
    """Read command lines, skipping blank lines and comments.

    The whole file is read before the first command runs, so an unparsable line
    stops the batch before it has done anything, rather than halfway through.

    :param infile: file object, one command per line as written after ``invenio``.
    :returns: list of (line number, argument list) tuples.
    :raises click.ClickException: on a line the shell lexer cannot split.
    """
    commands = []
    for number, line in enumerate(infile, start=1):
        if (line := line.strip()) and not line.startswith("#"):
            try:
                commands.append((number, shlex.split(line)))
            except ValueError as error:
                # unbalanced quotes raise a bare ValueError, which would surface
                # as a traceback where every other failure here is reported.
                raise click.ClickException(f"cannot parse line {number}: {error}") from error
    return commands


def run_command(root, root_ctx, args):
    """Run one command in the current application process.

    :param root: the root click group, used to resolve the command.
    :param root_ctx: context holding the ``ScriptInfo`` with the loaded application.
    :param args: argument list, as written after ``invenio``.
    :returns: None on success, the failure reason otherwise.
    """
    try:
        root.main(args=args, prog_name="invenio", standalone_mode=False, obj=root_ctx.obj)
    except SystemExit as error:
        # several commands report failure with a bare `sys.exit`, which would
        # otherwise take down the whole batch. A zero code means success.
        return error.code or None
    except Exception as error:
        return error
    return None


def reset_state(refresh, rollback=False):
    """Restore between two commands what separate processes gave for free.

    A fresh process starts with an empty session and, because building the
    application takes longer than the search refresh interval, with all
    previously indexed records already searchable. Chaining commands in a single
    process removes both guarantees.

    :param refresh: refresh the search indices.
    :param rollback: discard the session instead of committing it.
    """
    if rollback:
        db.session.rollback()
    else:
        db.session.commit()
    db.session.remove()
    if refresh:
        current_search_client.indices.refresh(index="_all")


@click.command("batch")
@click.argument("infile", type=click.File("r"))
@click.option("-k", "--continue-on-error", is_flag=True, default=False)
@click.option("-t", "--time", "show_time", is_flag=True, default=False)
@click.option("--no-refresh", is_flag=True, default=False)
@with_appcontext
def batch(infile, continue_on_error, show_time, no_refresh):
    """Run several invenio commands in a single application process.

    Each line of INFILE is a command as it would be written after `invenio`;
    blank lines and lines starting with `#` are ignored. Building the
    application costs about three seconds, so grouping commands this way rather
    than spawning one process each is what makes the difference on long
    sequences.

    Each line is resolved against the root command group, so any command the
    instance exposes can be used, whatever the group it belongs to.

    INFILE accepts the three usual forms, `-` meaning standard input, which a
    heredoc can feed as well as a pipe:

      invenio rero batch commands.batch

      build_commands | invenio rero batch -

      invenio rero batch <(build_commands)

    The last two need no temporary file. A setup script is better off with the
    process substitution, which keeps the command in the foreground so that a
    `time` prefix still measures it.
    """
    root_ctx = click.get_current_context().find_root()
    failures = []
    reset_total = 0

    for number, args in read_commands(infile):
        click.secho(f"[batch:{number}] invenio {shlex.join(args)}", fg="blue")
        start = time.perf_counter()
        failure = run_command(root_ctx.command, root_ctx, args)
        elapsed = time.perf_counter() - start
        if failure is not None:
            failures.append(number)
            click.secho(f"[batch:{number}] failed: {failure}", fg="red")
        try:
            start = time.perf_counter()
            reset_state(refresh=not no_refresh, rollback=failure is not None)
            reset_elapsed = time.perf_counter() - start
        except Exception as error:
            # without the session and index barriers the next commands would
            # silently read stale data: stop rather than carry on.
            raise click.ClickException(f"cannot reset state after line {number}: {error}") from error
        reset_total += reset_elapsed
        # the reset is reported apart: it replaces the implicit barrier that the
        # process startup used to provide, and is the batch's own overhead.
        if show_time:
            click.secho(f"[batch:{number}] {elapsed:.2f}s + {reset_elapsed:.2f}s reset", fg="yellow")
        if failure is not None and not continue_on_error:
            break

    if show_time:
        click.secho(f"[batch] reset total: {reset_total:.2f}s", fg="yellow")

    if failures:
        lines = ", ".join(str(number) for number in failures)
        raise click.ClickException(f"batch failed on line(s): {lines}")
