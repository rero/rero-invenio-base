# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click elasticsearch command-line utilities."""

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
@click.argument("paths", nargs=-1)
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
    """Check json files."""
    click.secho("Testing JSON indentation.", fg="green")
    files_list = []
    for path in paths:
        if os.path.isfile(path):
            files_list.append(path)
        elif os.path.isdir(path):
            files_list = files_list + glob(os.path.join(path, "**/*.json"), recursive=True)
    if not paths:
        files_list = glob("**/*.json", recursive=True)
    tot_error_cnt = 0
    for path_file in files_list:
        error_cnt = 0
        try:
            fname = path_file
            with open(fname) as opened_file:
                json_orig = opened_file.read().rstrip()
                opened_file.seek(0)
                json_file = json.load(opened_file, object_pairs_hook=OrderedDict)
            json_dump = json.dumps(json_file, indent=indent).rstrip()
            if json_dump != json_orig:
                error_cnt = 1
            if replace:
                with open(fname, "w") as opened_file:
                    opened_file.write(json.dumps(json_file, indent=indent, sort_keys=sort_keys))
                click.echo(f"{fname}: ", nl=False)
                click.secho("File replaced", fg="yellow")
            elif error_cnt == 0 and verbose:
                click.echo(f"{fname}: ", nl=False)
                click.secho("Well indented", fg="green")
            else:
                click.echo(f"{fname}: ", nl=False)
                click.secho("Bad indentation", fg="red")
        except ValueError as error:
            click.echo(f"{fname}: ", nl=False)
            click.secho("Invalid JSON", fg="red", nl=False)
            click.echo(f" -- {error}")
            error_cnt = 1

        tot_error_cnt += error_cnt

    sys.exit(tot_error_cnt)


__all__ = "utils"
