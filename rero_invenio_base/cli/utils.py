# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Click miscellaneous command-line utilities."""

import itertools
import json
import os
import subprocess
import sys
from collections import OrderedDict
from glob import glob

import click
from celery import current_app as celery_app
from flask import current_app
from flask.cli import with_appcontext
from invenio_db import db
from invenio_oauth2server.cli import process_scopes, process_user
from invenio_oauth2server.models import Client, Token
from werkzeug.security import gen_salt

SPDX_TAGS = ("SPDX-FileCopyrightText:", "SPDX-License-Identifier: AGPL-3.0-or-later")
SPDX_EXTENSIONS = (".cfg", ".conf", ".css", ".html", ".ini", ".js", ".md", ".py", ".scss", ".sh", ".toml", ".yml")
# `.github` templates and the changelog have no license header
SPDX_EXCLUDED_PATHS = (".github/", "CHANGELOG.md")


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


def needs_spdx_header(file_name, excluded=SPDX_EXCLUDED_PATHS):
    """Check if a file is expected to have a SPDX license header.

    Files are selected by extension. Files without extension are selected when
    they are Dockerfiles or scripts starting with a shebang.

    :param file_name: the path of the file to check.
    :param excluded: path parts of the files to skip.
    :returns: True if the file requires a SPDX license header.
    """
    if any(path in file_name for path in excluded):
        return False
    base_name = os.path.basename(file_name)
    if base_name.startswith("Dockerfile"):
        return True
    if extension := os.path.splitext(base_name)[1]:
        return extension in SPDX_EXTENSIONS
    with open(file_name, "rb") as opened_file:
        return opened_file.read(2) == b"#!"


def has_spdx_header(file_name):
    """Check if a file starts with the SPDX license header.

    The comment syntax is not checked, only the presence of both SPDX tags in
    the first lines of the file.

    :param file_name: the path of the file to check.
    :returns: True if the copyright and the license tags are both present.
    """
    with open(file_name, encoding="utf-8", errors="replace") as opened_file:
        header = "".join(itertools.islice(opened_file, 5))
    return all(tag in header for tag in SPDX_TAGS)


@utils.command("check_license")
@click.option(
    "-e",
    "--exclude",
    "excluded",
    multiple=True,
    help="Path part of the files to skip, on top of `.github/` and `CHANGELOG.md`.",
)
@click.option("-v", "--verbose", "verbose", is_flag=True, default=False)
def check_license(excluded, verbose):
    """Check the SPDX license headers of the files tracked by git.

    Exits 1 when a file misses its header.
    """
    click.secho("Testing SPDX license headers.", fg="green")
    try:
        tracked_files = subprocess.check_output(["git", "ls-files", "-z"], text=True).split("\0")
    except (OSError, subprocess.CalledProcessError) as error:
        raise click.ClickException("git is required and must run in a git repository.") from error
    excluded = SPDX_EXCLUDED_PATHS + excluded
    error_cnt = 0
    for file_name in tracked_files:
        if not os.path.isfile(file_name) or not needs_spdx_header(file_name, excluded):
            continue
        if has_spdx_header(file_name):
            if verbose:
                click.echo(f"{file_name}: ", nl=False)
                click.secho("License header found", fg="green")
        else:
            click.echo(f"{file_name}: ", nl=False)
            click.secho("Missing license header", fg="red")
            error_cnt += 1
    if error_cnt:
        click.secho(f"{error_cnt} file(s) with errors.", fg="red")
        sys.exit(1)


def create_personal(name, user_id, scopes=None, is_internal=False, access_token=None):
    """Create a personal access token.

    A token that is bound to a specific user and which doesn't expire, i.e.
    similar to the concept of an API key.

    :param name: client name.
    :param user_id: user ID.
    :param scopes: the list of permitted scopes.
    :param is_internal: if True, it is an internal access token.
    :param access_token: the token value, generated when not given.
    :returns: the new access token.
    """
    with db.session.begin_nested():
        scopes = " ".join(scopes) if scopes else ""
        client = Client(
            name=name,
            user_id=user_id,
            is_internal=True,
            is_confidential=False,
            _default_scopes=scopes,
        )
        client.gen_salt()
        if not access_token:
            access_token = gen_salt(current_app.config.get("OAUTH2SERVER_TOKEN_PERSONAL_SALT_LEN"))
        token = Token(
            client_id=client.client_id,
            user_id=user_id,
            access_token=access_token,
            expires=None,
            _scopes=scopes,
            is_personal=True,
            is_internal=is_internal,
        )
        db.session.add(client)
        db.session.add(token)
    return token


@utils.command("token-create")
@click.option("-n", "--name", required=True)
@click.option("-u", "--user", required=True, callback=process_user, help="User ID or email.")
@click.option("-s", "--scope", "scopes", multiple=True, callback=process_scopes)
@click.option("-i", "--internal", is_flag=True)
@click.option("-t", "--access_token", "access_token", required=False, help="personalized access_token.")
@with_appcontext
def token_create(name, user, scopes, internal, access_token):
    """Create a personal OAuth token and print it.

    Exits 1 when the user does not exist.
    """
    if not user:
        raise click.ClickException("No user found.")
    token = create_personal(name, user.id, scopes=scopes, is_internal=internal, access_token=access_token)
    db.session.commit()
    click.secho(token.access_token, fg="blue")


@utils.command("schedules")
@with_appcontext
def schedules():
    """List the periodic tasks of the Celery beat schedule."""
    for name, schedule in celery_app.conf.beat_schedule.items():
        click.echo(f"{name}\t{schedule}")


__all__ = ["utils"]
