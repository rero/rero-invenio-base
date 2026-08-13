<!--
SPDX-FileCopyrightText: Fondation RERO+
SPDX-License-Identifier: AGPL-3.0-or-later
-->

# rero-invenio-base Claude guide

## Overview

rero-invenio-base is a Python library providing generic backend utilities for RERO Invenio instances. It ships SEARCH CLI management commands, a streaming data export framework, and shared Celery tasks.

## Commands

All commands are run through uv's virtual env with `uv run`.

### Linting and formatting

**IMPORTANT:** After editing files, make sure that there are no errors in the formatting and linting.

```bash
uv run poe lint     # ruff check
uv run poe format   # ruff format
```

### Setup (done by humans)

Human developers will start the required containers and services on their own terms. Tests require SEARCH to be running.

## Architecture

### Export module

`ExportResource` is a `ContentNegotiatedMethodView` that streams record search results. Routes are registered dynamically from the `RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS` config key via `create_blueprint_from_app`. Each endpoint maps MIME types to serializers and prepends `/export` to the list route.

## Code style

- Be clear and concise in docstrings; do not over-comment the code.
- Do not use Python type annotations (no `-> str`, `: str`, etc. in signatures).
- Ruff is configured in `pyproject.toml`: `line-length = 120` and the excluded files under `[tool.ruff]`, the enabled rule sets under `[tool.ruff.lint]`, and the pep257 docstring convention under `[tool.ruff.lint.pydocstyle]`.
- Since Python 3.14 (PEP 758), parentheses around multiple exception types are optional when the `except`/`except*` clause has no `as` target: `except AttributeError, UnboundLocalError:` is valid and equivalent to `except (AttributeError, UnboundLocalError):` — not the old Python 2 comma syntax. `ruff format` removes the parentheses in that case; this is expected, not a bug. Parentheses are still required when binding the exception: `except (AttributeError, UnboundLocalError) as error:`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org).

## Testing

- Tests use function-based style (no class-based tests).
- The project follows a test-driven development methodology. Each commit must be accompanied by tests that ensure that the functionality works as intended. Tests must follow DRY principles and should only test specific app behaviour and not the behaviour of external modules (e.g. invenio dependencies).
- `--doctest-modules` is active and `testpaths` includes `rero_invenio_base`, so any `>>>` example written in a docstring is collected and run as a test.

### Running the tests (done by humans)

Human developers run tests from their consoles after starting the SEARCH container:

```bash
uv run ./scripts/test   # full suite (lint + pip-audit + pytest with SEARCH)
uv run pytest           # pytest only (SEARCH must already be running)
```
