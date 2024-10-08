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

import click

from .alias import alias
from .index import index
from .slm import slm
from .snapshot import snapshot
from .task import task


@click.group()
def es():
    """Elasticsarch management commands."""


es.add_command(index)
es.add_command(alias)
es.add_command(slm)
es.add_command(snapshot)
es.add_command(task)

__all__ = "index"
