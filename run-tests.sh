#!/usr/bin/env bash
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


# Usage:
#   env DB=postgresql12 SEARCH=elasticsearch7 CACHE=redis MQ=rabbitmq ./run-tests.sh

# Quit on errors
set -o errexit

# Quit on unbound symbols
set -o nounset

# Always bring down docker services
function cleanup() {
    # Note: for now we do not need this for the tests.
    # eval "$(docker-services-cli down --env)"
    echo "Done"
}
trap cleanup EXIT

# Check vulnerabilities:
#
# Exception are
# +============================+===========+==========================+==========+
# | package                    | installed | affected                 | ID       |
# +============================+===========+==========================+==========+
# | sqlalchemy                 | 1.4.46    | <2.0.0b1                 | 51668    |
# | sqlalchemy-utils           | 0.38.3    | >=0.27.0                 | 42194    |
# | py                         | 1.11.0    | <=1.11.0                 | 51457    |
# | safety                     | 1.10.3    | <2.2.0                   | 51358    |
# | wheel                      | 0.37.1    | <0.38.1                  | 51499    |
# +==============================================================================+
safety check -i 51668 -i 42194 -i 51457 -i 51358 -i 51499

flask rero utils check_license check_license_config.yml
pydocstyle rero_ils tests docs
isort --check-only --diff rero_invenio_base tests
autoflake -c -r --remove-all-unused-imports --ignore-init-module-imports . &> /dev/null || {
    autoflake --remove-all-unused-imports -ri --ignore-init-module-imports .
    exit 1
}

python -m sphinx.cmd.build -qnNW docs docs/_build/html
# Note: for now we do not need this for the tests.
export DOCKER_SERVICES_FILEPATH=./docker-services.yml
eval "$(docker-services-cli up --search ${SEARCH:-elasticsearch} --env)"
python -m pytest
tests_exit_code=$?
python -m sphinx.cmd.build -qnNW -b doctest docs docs/_build/doctest
exit "$tests_exit_code"
