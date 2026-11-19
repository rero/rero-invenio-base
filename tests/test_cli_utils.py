# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli utils commands."""

import json
import subprocess
import sys
from importlib.metadata import entry_points
from types import SimpleNamespace

import pytest
from click.testing import CliRunner
from invenio_accounts.models import User
from invenio_oauth2server import config as oauth2server_config
from invenio_oauth2server.models import Token

from rero_invenio_base.cli.utils import (
    SPDX_EXCLUDED_PATHS,
    check_json,
    check_license,
    has_spdx_header,
    needs_spdx_header,
    schedules,
    token_create,
)

DATA = {"key": "value", "list": [1, 2]}


def _write(path, indent=2):
    """Write DATA as JSON with the given indentation and return its path."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(DATA, indent=indent) + "\n")
    return str(path)


def test_check_json_well_indented(tmp_path):
    """A well indented file passes quietly, and is listed with --verbose."""
    path = _write(tmp_path / "good.json")
    res = CliRunner().invoke(check_json, [path])
    assert res.exit_code == 0
    assert path not in res.output
    res = CliRunner().invoke(check_json, [path, "--verbose"])
    assert res.exit_code == 0
    assert f"{path}: Well indented" in res.output


def test_check_json_non_ascii(tmp_path):
    """Non-ASCII characters pass both escaped and written as is."""
    for name, escaped in (("escaped.json", True), ("literal.json", False)):
        path = tmp_path / name
        path.write_text(json.dumps({"title": "Bibliothèque"}, indent=2, ensure_ascii=escaped), encoding="utf-8")
    res = CliRunner().invoke(check_json, [str(tmp_path)])
    assert res.exit_code == 0, res.output


def test_check_json_bad_indentation(tmp_path):
    """A badly indented file is reported and makes the check fail."""
    path = _write(tmp_path / "bad.json", indent=4)
    res = CliRunner().invoke(check_json, [path])
    assert res.exit_code == 1
    assert f"{path}: Bad indentation" in res.output
    assert "1 file(s) with errors." in res.output


def test_check_json_invalid(tmp_path):
    """An unparsable file is reported as invalid JSON."""
    path = tmp_path / "invalid.json"
    path.write_text('{"key": }')
    res = CliRunner().invoke(check_json, [str(path)])
    assert res.exit_code == 1
    assert f"{path}: Invalid JSON" in res.output


def test_check_json_walks_directories(tmp_path):
    """A directory is searched recursively and only bad files are listed."""
    good = _write(tmp_path / "good.json")
    bad = _write(tmp_path / "nested" / "bad.json", indent=4)
    res = CliRunner().invoke(check_json, [str(tmp_path)])
    assert res.exit_code == 1
    assert good not in res.output
    assert f"{bad}: Bad indentation" in res.output


def test_check_json_many_errors_still_fail(tmp_path):
    """The exit status stays 1 past 255 errors instead of wrapping to 0."""
    for number in range(256):
        _write(tmp_path / f"{number}.json", indent=4)
    res = CliRunner().invoke(check_json, [str(tmp_path)])
    assert res.exit_code == 1
    assert "256 file(s) with errors." in res.output


def test_check_json_missing_path(tmp_path):
    """A path that does not exist is a usage error, not a silent pass."""
    res = CliRunner().invoke(check_json, [str(tmp_path / "typo")])
    assert res.exit_code == 2
    assert "does not exist" in res.output


def test_check_json_requires_a_path():
    """Without a path the command stops, rather than walk the whole current directory."""
    res = CliRunner().invoke(check_json, [])
    assert res.exit_code == 2
    assert "Missing argument 'PATHS...'" in res.output


def test_check_json_replace(tmp_path):
    """--replace rewrites only the bad files, which then no longer count as errors."""
    good = tmp_path / "good.json"
    good.write_text(json.dumps(DATA, indent=2, ensure_ascii=False))  # well indented, no final newline
    bad = _write(tmp_path / "bad.json", indent=4)
    res = CliRunner().invoke(check_json, [str(tmp_path), "--replace", "--indent", "2"])
    assert res.exit_code == 0, res.output
    assert f"{bad}: File replaced" in res.output
    assert str(good) not in res.output
    assert (tmp_path / "bad.json").read_text() == json.dumps(DATA, indent=2) + "\n"
    assert good.read_text() == json.dumps(DATA, indent=2, ensure_ascii=False)


def test_check_json_sort_keys(tmp_path):
    """--sort-keys checks the key order, and --replace sorts the keys."""
    path = tmp_path / "unsorted.json"
    path.write_text(json.dumps({"b": 1, "a": 2}, indent=2) + "\n")
    assert CliRunner().invoke(check_json, [str(path)]).exit_code == 0
    res = CliRunner().invoke(check_json, [str(path), "--sort-keys"])
    assert res.exit_code == 1
    assert f"{path}: Bad indentation or key order" in res.output
    res = CliRunner().invoke(check_json, [str(path), "--sort-keys", "--replace"])
    assert res.exit_code == 0
    assert path.read_text() == json.dumps({"a": 2, "b": 1}, indent=2) + "\n"


def test_check_json_console_script():
    """The command is installed as the standalone check_json script."""
    (script,) = entry_points(group="console_scripts", name="check_json")
    assert script.load() is check_json


def test_needs_spdx_header(tmp_path):
    """Files are selected by extension, Dockerfile or shebang, and excluded by path."""
    (script := tmp_path / "server").write_text("#!/usr/bin/env bash\necho\n")
    (plain := tmp_path / "LICENSE").write_text("GNU AFFERO GENERAL PUBLIC LICENSE\n")

    assert needs_spdx_header("rero_invenio_base/cli/utils.py")
    assert needs_spdx_header("docker/nginx/Dockerfile")
    assert needs_spdx_header(str(script))
    assert not needs_spdx_header(str(plain))
    assert not needs_spdx_header("tests/data/documents.json")
    assert not needs_spdx_header("templates/email/notice.txt")
    assert not needs_spdx_header(".github/workflows/release.yml")
    assert not needs_spdx_header("CHANGELOG.md")
    assert needs_spdx_header("data/wiki/home_en.md")
    assert not needs_spdx_header("data/wiki/home_en.md", (*SPDX_EXCLUDED_PATHS, "data/wiki/"))


def test_has_spdx_header(tmp_path):
    """Both tags must be in the first lines, whatever the comment syntax."""
    copyright_tag = "SPDX-FileCopyrightText: Fondation RERO+"
    license_tag = "SPDX-License-Identifier: AGPL-3.0-or-later"

    def write(name, content):
        (file_path := tmp_path / name).write_text(content)
        return str(file_path)

    assert has_spdx_header(write("api.py", f"# {copyright_tag}\n# {license_tag}\n"))
    assert has_spdx_header(write("page.html", f"{{# {copyright_tag} #}}\n{{# {license_tag} #}}\n"))
    assert has_spdx_header(write("README.md", f"<!--\n{copyright_tag}\n{license_tag}\n-->\n"))
    # missing tag, wrong license and header pushed out of the first lines
    assert not has_spdx_header(write("no_license.py", f"# {copyright_tag}\n"))
    assert not has_spdx_header(write("wrong_license.py", f"# {copyright_tag}\n# SPDX-License-Identifier: MIT\n"))
    assert not has_spdx_header(write("too_late.py", f"{'\n' * 5}# {copyright_tag}\n# {license_tag}\n"))


HEADER = "# SPDX-FileCopyrightText: Fondation RERO+\n# SPDX-License-Identifier: AGPL-3.0-or-later\n"


def _git_repo(tmp_path, monkeypatch, files):
    """Commit the files to a new git repository and make it the current directory.

    :param files: content by relative path.
    """
    for name, content in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    monkeypatch.chdir(tmp_path)


def test_check_license_headers(tmp_path, monkeypatch):
    """Files with a header pass, the selected files without one make the check fail."""
    _git_repo(
        tmp_path,
        monkeypatch,
        {
            "good.py": HEADER + "x = 1\n",
            "bad.py": "x = 1\n",
            "run": "#!/bin/sh\necho\n",
            "Dockerfile": "FROM python\n",
            "notes.txt": "no header needed\n",
            "CHANGELOG.md": "# Changelog\n",
            ".github/pull_request_template.md": "template\n",
        },
    )
    res = CliRunner().invoke(check_license, [])
    assert res.exit_code == 1
    for name in ("bad.py", "run", "Dockerfile"):
        assert f"{name}: Missing license header" in res.output
    for name in ("good.py", "notes.txt", "CHANGELOG.md", ".github/"):
        assert name not in res.output
    assert "3 file(s) with errors." in res.output
    res = CliRunner().invoke(check_license, ["--verbose"])
    assert "good.py: License header found" in res.output


def test_check_license_exclude(tmp_path, monkeypatch):
    """--exclude skips the given paths on top of the default ones."""
    _git_repo(tmp_path, monkeypatch, {"good.py": HEADER, "data/wiki/page.md": "page\n"})
    assert CliRunner().invoke(check_license, []).exit_code == 1
    res = CliRunner().invoke(check_license, ["-e", "data/wiki/"])
    assert res.exit_code == 0, res.output


def test_check_license_outside_git(tmp_path, monkeypatch):
    """Without a git repository the check stops with an explicit error."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GIT_CEILING_DIRECTORIES", str(tmp_path.parent))
    res = CliRunner().invoke(check_license, [])
    assert res.exit_code == 1
    assert "git is required and must run in a git repository." in res.output


def test_schedules(app, monkeypatch):
    """Each periodic task of the beat schedule is listed with its schedule."""
    monkeypatch.setattr(
        sys.modules[schedules.callback.__module__],
        "celery_app",
        SimpleNamespace(conf=SimpleNamespace(beat_schedule={"harvest": {"task": "harvest", "schedule": 60}})),
    )
    res = CliRunner().invoke(schedules, [])
    assert res.exit_code == 0
    assert "harvest\t{'task': 'harvest', 'schedule': 60}" in res.output


@pytest.fixture
def oauth2server_app(app, db, monkeypatch):
    """Give the app the OAuth2 server settings, which its extension sets in an instance."""
    for key in dir(oauth2server_config):
        if key.startswith("OAUTH2SERVER_"):
            monkeypatch.setitem(app.config, key, getattr(oauth2server_config, key))
    return app


def test_token_create(oauth2server_app, db):
    """A personal token is created for the user given by email or ID, with the given value or a generated one."""
    user = User(email="admin@rero.ch", active=True)
    db.session.add(user)
    db.session.commit()
    res = CliRunner().invoke(token_create, ["-n", "monitoring", "-u", "admin@rero.ch", "-t", "my-token"])
    assert res.exit_code == 0, res.output
    assert res.output.strip() == "my-token"
    token = Token.query.filter_by(access_token="my-token").one()
    assert (token.user_id, token.is_personal, token.client.name) == (user.id, True, "monitoring")

    res = CliRunner().invoke(token_create, ["-n", "other", "-u", str(user.id)])
    assert res.exit_code == 0, res.output
    assert len(res.output.strip()) == oauth2server_config.OAUTH2SERVER_TOKEN_PERSONAL_SALT_LEN


def test_token_create_unknown_user(oauth2server_app):
    """An unknown user stops the command with an error instead of creating nothing silently."""
    res = CliRunner().invoke(token_create, ["-n", "monitoring", "-u", "nobody@rero.ch"])
    assert res.exit_code == 1
    assert "No user found." in res.output
