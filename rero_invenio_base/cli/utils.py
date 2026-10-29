# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click miscellaneous command-line utilities."""

import json
import os
import sys
from collections import OrderedDict
from glob import glob

import click


@click.group()
def utils():
    """Misc management commands."""


@utils.command("check_json")
@click.argument("paths", nargs=-1, type=click.Path(exists=True))
@click.option(
    "-r",
    "--replace",
    "replace",
    is_flag=True,
    default=False,
    help="change file in place default=False",
)
@click.option(
    "-s",
    "--sort-keys",
    "sort_keys",
    is_flag=True,
    default=False,
    help="order keys during replacement default=False",
)
@click.option("-i", "--indent", "indent", type=click.INT, default=2, help="indent default=2")
@click.option("-v", "--verbose", "verbose", is_flag=True, default=False)
def check_json(paths, replace, indent, sort_keys, verbose):
    """Check the indentation of JSON files.

    PATHS are files, or directories searched recursively for ``*.json`` files;
    without any, the current directory is searched. Exits 1 when a file is
    badly indented or invalid.
    """
    click.secho("Testing JSON indentation.", fg="green")
    files_list = []
    for path in paths:
        if os.path.isfile(path):
            files_list.append(path)
        elif os.path.isdir(path):
            files_list += glob(os.path.join(path, "**/*.json"), recursive=True)
    if not paths:
        files_list = glob("**/*.json", recursive=True)
    tot_error_cnt = 0
    for path_file in files_list:
        error_cnt = 0
        try:
            fname = path_file
            with open(fname, encoding="utf-8") as opened_file:
                json_orig = opened_file.read().rstrip()
                opened_file.seek(0)
                json_file = json.load(opened_file, object_pairs_hook=OrderedDict)
            # non-ASCII characters are accepted both escaped and written as is.
            well_indented = {
                json.dumps(json_file, indent=indent, ensure_ascii=escaped).rstrip() for escaped in (True, False)
            }
            if json_orig not in well_indented:
                error_cnt = 1
            if replace:
                with open(fname, "w", encoding="utf-8") as opened_file:
                    opened_file.write(json.dumps(json_file, indent=indent, sort_keys=sort_keys) + "\n")
                click.echo(f"{fname}: ", nl=False)
                click.secho("File replaced", fg="yellow")
            elif error_cnt:
                click.echo(f"{fname}: ", nl=False)
                click.secho("Bad indentation", fg="red")
            elif verbose:
                click.echo(f"{fname}: ", nl=False)
                click.secho("Well indented", fg="green")
        except ValueError as error:
            click.echo(f"{fname}: ", nl=False)
            click.secho("Invalid JSON", fg="red", nl=False)
            click.echo(f" -- {error}")
            error_cnt = 1

        tot_error_cnt += error_cnt

    # an exit status wraps around at 256, so the count cannot be returned as is.
    if tot_error_cnt:
        click.secho(f"{tot_error_cnt} file(s) with errors.", fg="red")
        sys.exit(1)


__all__ = ["utils"]
