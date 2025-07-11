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

"""Test cli elasticsearch commands.

For the tests we need Elasticsearch with xpack.
xpack is only available in non OSS Elasticsearch versions.
We have to use a newer ES version and an `docker-services-cli` version
without OSS dependencies for SLM tests.
"""


# from rero_invenio_base.cli.es.slm.cli import stats, status

# def test_cli_es_index_alias(script_info, app, es_runner):
#     """Test index and aliases command line interface."""

#     runner = es_runner
#     res = runner.invoke(
#         status,
#         [],
#         obj=script_info
#     )
#     assert res.exit_code == 0

#     res = runner.invoke(
#         stats,
#         [],
#         obj=script_info
#     )
#     assert res.exit_code == 0
