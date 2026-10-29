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
@click.argument("paths", nargs=-1, required=True, type=click.Path(exists=True))
@click.option(
    "-r",
    "--replace",
    "replace",
    is_flag=True,
    default=False,
    help="Rewrite the badly formatted files in place.",
)
@click.option(
    "-s",
    "--sort-keys",
    "sort_keys",
    is_flag=True,
    default=False,
    help="Require the keys in sorted order, and sort them with --replace.",
)
@click.option("-i", "--indent", "indent", type=click.INT, default=2, help="indent default=2")
@click.option("-v", "--verbose", "verbose", is_flag=True, default=False)
def check_json(paths, replace, indent, sort_keys, verbose):
    """Check the indentation of JSON files.

    PATHS are files, or directories searched recursively for ``*.json`` files.
    Exits 1 when a file is invalid, or badly formatted and not replaced.
    """
    click.secho("Testing JSON indentation.", fg="green")
    files_list = []
    for path in paths:
        if os.path.isfile(path):
            files_list.append(path)
        elif os.path.isdir(path):
            files_list += glob(os.path.join(path, "**/*.json"), recursive=True)
    tot_error_cnt = 0
    for fname in files_list:
        try:
            with open(fname, encoding="utf-8") as opened_file:
                json_orig = opened_file.read().rstrip()
                opened_file.seek(0)
                json_file = json.load(opened_file, object_pairs_hook=OrderedDict)
        except ValueError as error:
            click.echo(f"{fname}: ", nl=False)
            click.secho("Invalid JSON", fg="red", nl=False)
            click.echo(f" -- {error}")
            tot_error_cnt += 1
            continue
        # non-ASCII characters are accepted both escaped and written as is.
        well_formatted = {
            json.dumps(json_file, indent=indent, sort_keys=sort_keys, ensure_ascii=escaped).rstrip()
            for escaped in (True, False)
        }
        if json_orig in well_formatted:
            if verbose:
                click.echo(f"{fname}: ", nl=False)
                click.secho("Well indented", fg="green")
        elif replace:
            with open(fname, "w", encoding="utf-8") as opened_file:
                opened_file.write(json.dumps(json_file, indent=indent, sort_keys=sort_keys) + "\n")
            click.echo(f"{fname}: ", nl=False)
            click.secho("File replaced", fg="yellow")
        else:
            click.echo(f"{fname}: ", nl=False)
            click.secho("Bad indentation or key order" if sort_keys else "Bad indentation", fg="red")
            tot_error_cnt += 1

    # an exit status wraps around at 256, so the count cannot be returned as is.
    if tot_error_cnt:
        click.secho(f"{tot_error_cnt} file(s) with errors.", fg="red")
        sys.exit(1)


__all__ = ["utils"]
