<!--
SPDX-FileCopyrightText: Fondation RERO+
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# Changelog

<!-- version list -->

## v1.2.0 (2026-08-18)

### Chores

- Update dependencies
  ([`4588e29`](https://github.com/rero/rero-invenio-base/commit/4588e2967d57dc81559abf429600dcdcdb769a8d))

### Continuous Integration

- Bump actions to their latest releases
  ([`aa4e5a1`](https://github.com/rero/rero-invenio-base/commit/aa4e5a130b1af637041c24c8654f805b40a3ac5f))

### Documentation

- Keep only non-derivable rules in CLAUDE.md
  ([`5f0b6a8`](https://github.com/rero/rero-invenio-base/commit/5f0b6a8351882ffb9b0bcbcb850a4693af74f15d))

### Features

- **export**: Add streamed XLSX support
  ([`0482148`](https://github.com/rero/rero-invenio-base/commit/048214825a29bf3ebcc1e95f66154eef9981eca7))


## v1.1.2 (2026-07-09)

### Bug Fixes

- **es**: Refresh dest index before counting docs
  ([`f815e09`](https://github.com/rero/rero-invenio-base/commit/f815e092deeb33a2ced611d76ba4c0db413fde48))


## v1.1.1 (2026-07-06)

### Bug Fixes

- **es**: Use long-polling to watch reindex tasks
  ([`bb7547e`](https://github.com/rero/rero-invenio-base/commit/bb7547ef4c53306e565d88a5d885399d55b337a6))


## v1.1.0 (2026-06-22)

### Chores

- Drop Python 3.10/3.11, fix ruff UP017 and UP047
  ([`ba68ba4`](https://github.com/rero/rero-invenio-base/commit/ba68ba4fa15044c004eae95f446b8855ac1e8062))

- Update dependencies
  ([`bef4874`](https://github.com/rero/rero-invenio-base/commit/bef4874fdc07ead1b624335cd4b24b775a445a41))

### Code Style

- Replace verbose license headers with SPDX tags
  ([`f16d053`](https://github.com/rero/rero-invenio-base/commit/f16d053f9612690ffd2af9a20f5a9a8baf462cbb))

### Continuous Integration

- Add automatic release publication and repo automation
  ([`a8d6268`](https://github.com/rero/rero-invenio-base/commit/a8d6268d34ff5fb4998b8794960f811917940634))

### Features

- **es**: Improve Search CLI with new commands and safer index management
  ([`08242e6`](https://github.com/rero/rero-invenio-base/commit/08242e6cae72d2287c5cbba117e5600056bbc122))


## [v1.0.0](https://github.com/rero/rero-invenio-base/tree/v1.0.0) (2026-05-06)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.3.3...v1.0.0)

**Breaking changes:**

* chore: update dependencies and Python 3.14 (by @PascalRepond)
  * Dropped Python <3.10 support

**Fixes:**

* fix(es): error handling in `update_mapping` (by @rerowep)

## [v0.3.3](https://github.com/rero/rero-invenio-base/tree/v0.3.3) (2025-08-05)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.3.2...v0.3.3)

* chore: use uv_publish as a build system (by @PascalRepond)

## [v0.3.2](https://github.com/rero/rero-invenio-base/tree/v0.3.2) (2025-07-31)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.3.1...v0.3.2)

**Changes:**

* feat(dev): add uv and ruff [#21](https://github.com/rero/rero-invenio-base/pull/21) (by @PascalRepond)
* chore(actions): pypi publish package use poetry [#20](https://github.com/rero/rero-invenio-base/pull/20) (by @PascalRepond)

## [v0.3.1](https://github.com/rero/rero-invenio-base/tree/v0.3.1) (2025-04-16)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.3.0...v0.3.1)

**Changes:**

* dependencies: fix vulnerabilities [\#18](https://github.com/rero/rero-invenio-base/pull/18) (by @rerowep)
* dependencies: remove restrictive dependencies [\#17](https://github.com/rero/rero-invenio-base/pull/17) (by @rerowep)

## [v0.3.0](https://github.com/rero/rero-invenio-base/tree/v0.3.0) (2023-12-21)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.2.1...v0.3.0)

**Changes:**

* dependencies: fix vulnerabilities [\#15](https://github.com/rero/rero-invenio-base/pull/15) (by @rerowep)

## [v0.2.1](https://github.com/rero/rero-invenio-base/tree/v0.2.1) (2023-05-10)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.2.0...v0.2.1)

**Changes:**

* es: task cli [\#12](https://github.com/rero/rero-invenio-base/pull/12) (by @rerowep)

## [v0.2.0](https://github.com/rero/rero-invenio-base/tree/v0.2.0) (2023-01-31)

[Full Changelog](https://github.com/rero/rero-invenio-base/compare/v0.1.0...v0.2.0)

**Changes:**

* task: add a generic celery task [\#10](https://github.com/rero/rero-invenio-base/pull/10) (by @jma)

## [v0.1.0](https://github.com/rero/rero-invenio-base/tree/v0.1.0) (2022-09-02)

**Changes:**

* cli: adds snapshot lifecycle management commands [\#6](https://github.com/rero/rero-invenio-base/pull/6) (by @rerowep)
* modules: create `export` module [\#7](https://github.com/rero/rero-invenio-base/pull/7) (by @zannkukai)
* index: add reindex command [\#5](https://github.com/rero/rero-invenio-base/pull/5) (by @jma)
* cli: add snapshot commmand line interfaces [\#4](https://github.com/rero/rero-invenio-base/pull/4) (by @jma)
