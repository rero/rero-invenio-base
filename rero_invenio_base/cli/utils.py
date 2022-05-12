# -*- coding: utf-8 -*-
#
# RERO Invenio Base
# Copyright (C) 2022 RERO.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, version 3 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.

"""Click elasticsearch command-line utilities."""

import difflib
import json
import os
import sys
from collections import OrderedDict
from glob import glob

import click
import yaml


@click.group()
def utils():
    """Misc management commands."""


@utils.command('check_json')
@click.argument('paths', nargs=-1)
@click.option(
    '-r', '--replace', 'replace', is_flag=True, default=False,
    help='change file in place default=False'
)
@click.option(
    '-s', '--sort-keys', 'sort_keys', is_flag=True, default=False,
    help='order keys during replacement default=False'
)
@click.option(
    '-i', '--indent', 'indent', type=click.INT, default=2,
    help='indent default=2'
)
@click.option('-v', '--verbose', 'verbose', is_flag=True, default=False)
def check_json(paths, replace, indent, sort_keys, verbose):
    """Check json files."""
    click.secho('Testing JSON indentation.', fg='green')
    files_list = []
    for path in paths:
        if os.path.isfile(path):
            files_list.append(path)
        elif os.path.isdir(path):
            files_list = files_list + glob(os.path.join(path, '**/*.json'),
                                           recursive=True)
    if not paths:
        files_list = glob('**/*.json', recursive=True)
    tot_error_cnt = 0
    for path_file in files_list:
        error_cnt = 0
        try:
            fname = path_file
            with open(fname, 'r') as opened_file:
                json_orig = opened_file.read().rstrip()
                opened_file.seek(0)
                json_file = json.load(opened_file,
                                      object_pairs_hook=OrderedDict)
            json_dump = json.dumps(json_file, indent=indent).rstrip()
            if json_dump != json_orig:
                error_cnt = 1
            if replace:
                with open(fname, 'w') as opened_file:
                    opened_file.write(json.dumps(json_file,
                                                 indent=indent,
                                                 sort_keys=sort_keys))
                click.echo(f'{fname}: ', nl=False)
                click.secho('File replaced', fg='yellow')
            elif error_cnt == 0 and verbose:
                click.echo(f'{fname}: ', nl=False)
                click.secho('Well indented', fg='green')
            else:
                click.echo(f'{fname}: ', nl=False)
                click.secho('Bad indentation', fg='red')
        except ValueError as error:
            click.echo(f'{fname}: ', nl=False)
            click.secho('Invalid JSON', fg='red', nl=False)
            click.echo(f' -- {error}')
            error_cnt = 1

        tot_error_cnt += error_cnt

    sys.exit(tot_error_cnt)


@utils.command('check_license')
@click.argument('configfile', type=click.File('r'), default=sys.stdin)
@click.option('-v', '--verbose', 'verbose', is_flag=True, default=False)
@click.option('-p', '--progress', 'progress', is_flag=True, default=False)
def check_license(configfile, verbose, progress):
    """Check licenses."""
    click.secho('Testing licenses in files.', fg='green')

    def get_files(paths, extensions, recursive=True):
        """Get files from paths."""
        files_list = []
        for path in paths:
            if os.path.isfile(path):
                files_list.append(path)
            elif os.path.isdir(path):
                for extension in extensions:
                    files_list += glob(
                        os.path.join(path, f'**/*.{extension}'),
                        recursive=recursive
                    )
        return files_list

    def delete_prefix(prefix, line):
        """Delete prefix from line."""
        if prefix:
            line = line.replace(prefix, "")
        return line.strip()

    def is_copyright(line):
        """Line is copyright."""
        if line.startswith('Copyright (C)'):
            return True
        return False

    def get_line(lines, index, prefix):
        """Get line on index."""
        line = delete_prefix(prefix, lines[index])
        return line, index+1

    def show_diff(linenbr, text, n_text):
        """Show string diffs."""
        seqm = difflib.SequenceMatcher(
            None,
            text.replace(' ', '◼︎'),
            n_text.replace(' ', '◼︎')
        )
        click.echo(f'{linenbr}: ', nl=False)
        for opcode, a0, a1, b0, b1 in seqm.get_opcodes():
            if opcode == 'equal':
                click.echo(seqm.a[a0:a1], nl=False)
            elif opcode == 'insert':
                click.secho(seqm.b[b0:b1], fg='red', nl=False)
            elif opcode == 'delete':
                click.secho(seqm.a[a0:a1], fg='blue', nl=False)
            elif opcode == 'replace':
                # seqm.a[a0:a1] -> seqm.b[b0:b1]
                click.secho(seqm.b[b0:b1], fg='green', nl=False)
        click.echo()

    def test_file(file_name, extensions, extension, license_lines,
                  verbose, progress):
        """Test the license in file."""
        if progress:
            click.secho('License test: ', fg='green', nl=False)
            click.echo(file_name)
        with open(file_name, 'r') as file:
            result = test_license(
                file=file,
                extension=extensions[extension],
                license_lines=license_lines,
                verbose=verbose
            )
            if result != []:
                click.secho(
                    f'License error in {file_name} in lines {result}',
                    fg='red'
                )
                # We have an error
                return 1
        # No error found
        return 0

    def is_slash_directive(file, line):
        is_js_file = file.name.split('.')[-1] == 'js'
        if is_js_file and re.search(triple_slash, line):
            return True
        return False

    def test_license(file, extension, license_lines, verbose):
        """Test the license in file."""
        lines_with_errors = []
        lines = [line.rstrip() for line in file]
        linenbr = 0
        linemaxnbr = len(lines)
        prefix = extension.get('prefix')
        line, linenbr = get_line(lines, linenbr, prefix)
        # Get over Shebang lines o Triple-Slash Directives (for Javascript
        # files)
        while lines[linenbr-1].startswith('#!') or \
                is_slash_directive(file, lines[linenbr-1]):
            # get over Shebang
            line, linenbr = get_line(lines, linenbr, prefix)
        if extension.get('top') and line not in extension.get('top'):
            if verbose:
                for t in extension['top']:
                    show_diff(linenbr, t, line)
            lines_with_errors.append(linenbr+1)
        line, linenbr = get_line(lines, linenbr, prefix)
        for license_line in license_lines:
            # compare the license lines
            if is_copyright(license_line):
                while is_copyright(line):
                    line, linenbr = get_line(lines, linenbr, prefix)
                linenbr -= 1
                line = 'Copyright (C)'
            if license_line != line:
                if verbose:
                    show_diff(linenbr, license_line, line)
                lines_with_errors.append(linenbr)
            # Fix crash while testing a file with only comments.
            if linenbr >= linemaxnbr:
                continue
            line, linenbr = get_line(lines, linenbr, prefix)
        return lines_with_errors

    config = yaml.safe_load(configfile)
    file_extensions = config['file_extensions']
    extensions = {}
    for file_extension in file_extensions:
        for ext in file_extension.split(','):
            extensions.setdefault(ext.strip(), file_extensions[file_extension])
    # create recursive file list
    files_list = get_files(
        paths=config['directories']['recursive'],
        extensions=extensions,
        recursive=True
    )
    # add flat file list
    files_list += get_files(
        paths=config['directories']['flat'],
        extensions=extensions,
        recursive=False
    )
    # remove excluded files
    exclude_list = []
    for ext in config['directories'].get('exclude', []):
        exclude_list += get_files(
            paths=config['directories']['exclude'][ext],
            extensions=[ext],
            recursive=True
        )
    files_list = list(set(files_list) - set(exclude_list))

    # set regexp expression for Triple-Slash directives
    triple_slash = r'^/// <reference \w*=\"\w*\" />$'

    license_lines = config['license_text'].split('\n')
    tot_error_cnt = 0
    for file_name in files_list:
        # test every file
        extension = os.path.splitext(file_name)[1][1:]
        tot_error_cnt += test_file(
            file_name=file_name,
            extensions=extensions,
            extension=extension,
            license_lines=license_lines,
            verbose=verbose,
            progress=progress
        )
    for extension in config.get('files', []):
        # test every files
        for file_name in config['files'][extension]:
            tot_error_cnt += test_file(
                file_name=file_name,
                extensions=extensions,
                extension=extension,
                license_lines=license_lines,
                verbose=verbose,
                progress=progress
            )

    sys.exit(tot_error_cnt)


__all__ = ('utils')
