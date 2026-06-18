# SPDX-FileCopyrightText: Fondation RERO+
# SPDX-License-Identifier: AGPL-3.0-or-later

"""RERO Invenio Base export module configuration file."""

"""
  This module must be used to create dynamic export route for resource
  configured by the `invenio-records-rest`. Exports endpoints will provide
  streamed content. The content is based on an ElasticSearch search result ;
  this result is processed using ElasticSearch `scan()` method tu fully
  implement streamed result.

  Each configured endpoint add a flask blueprint endpoint accessible using the
  `/export/{resource_list_route/` url.


.. code-block:: python

RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS = dict(
    loan=dict(
        resource={invenio-record-rest_resource_configuration_endpoint},
        default_media_type='text/csv',
        search_serializers={
            'text/csv': 'rero_ils.modules.loans.serializers:csv_stream_search',
        },
        search_serializers_aliases={
            'csv': 'text/csv'
        }
    )
)

:param resource: Pointer to the resource rest configuration endpoint from
    `invenio-record-rest`. Check `https://github.com/inveniosoftware/invenio-
    records-rest/blob/master/invenio_records_rest/config.py` to get correct
    resource configuration.

:param search_serializers: It contains the list of records serializers for all
    supported format. This configuration differ from the previous because in
    this case it handle a list of records resulted by a search query instead of
    a single record.

:param search_serializers_aliases: A mapping of values of the defined query arg
    (see `config.REST_MIMETYPE_QUERY_ARG_NAME`) to valid mimetypes for records
    search serializers: dict(alias -> mimetype).

"""
