# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

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
