<!--
SPDX-FileCopyrightText: Fondation RERO+
SPDX-License-Identifier: AGPL-3.0-or-later
-->

<!-- PROJECT SHIELDS -->
[![Github actions
status](https://github.com/rero/rero-invenio-base/actions/workflows/continuous-integration-test.yml/badge.svg)](https://github.com/rero/rero-invenio-base/actions/workflows/continuous-integration-test.yml)
[![Release
Number](https://img.shields.io/github/tag/rero/rero-invenio-base.svg)](https://github.com/rero/rero-invenio-base/releases/latest)
[![Downloads](https://img.shields.io/pypi/dm/rero-invenio-base.svg)](https://pypi.python.org/pypi/rero-invenio-base)
[![License](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](http://www.gnu.org/licenses/agpl-3.0.html)
[![uv](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/uv/main/assets/badge/v0.json)](https://github.com/astral-sh/uv)

Generic backend libraries for RERO Invenio instances.

## Security

The `rero_invenio_base.modules.tasks.run_on_worker` Celery task executes the
Python code it receives. It is registered on the workers of every instance that
installs this package, so anyone able to publish a message to the Celery broker
can run any code on those workers. Keep the broker on a private network and its
credentials secret.
