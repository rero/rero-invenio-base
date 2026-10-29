# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""Test cli utils commands."""

import json
from importlib.metadata import entry_points

from click.testing import CliRunner

from rero_invenio_base.cli.utils import check_json

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


def test_check_json_replace(tmp_path):
    """--replace rewrites the file with the indentation and a final newline."""
    path = _write(tmp_path / "bad.json", indent=4)
    res = CliRunner().invoke(check_json, [path, "--replace", "--indent", "2"])
    assert "File replaced" in res.output
    assert (tmp_path / "bad.json").read_text() == json.dumps(DATA, indent=2) + "\n"
    assert CliRunner().invoke(check_json, [path]).exit_code == 0


def test_check_json_console_script():
    """The command is installed as the standalone check_json script."""
    (script,) = entry_points(group="console_scripts", name="check_json")
    assert script.load() is check_json
