# rero-invenio-base Claude guide

## Overview

rero-invenio-base is a Python library providing generic backend utilities for RERO Invenio instances. It ships SEARCH CLI management commands, a streaming data export framework, and shared Celery tasks.

**Stack**: Python 3.14, Flask (Invenio), OpenSearch 2, Celery
**Package manager**: `uv` with `poethepoet` for task running

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

### Package structure

```text
rero_invenio_base/
├── ext.py                    # Flask extension (REROInvenioBase)
├── config.py                 # Default configuration keys
├── cli/
│   ├── shared.py             # Shared CLI helpers (abort_if_false)
│   ├── utils.py              # check_json command
│   └── search/
│       ├── alias.py          # `rero search alias` commands
│       ├── health.py         # `rero search health` connectivity check
│       ├── index.py          # `rero search index` commands (reindex, move, update-mapping, rebuild, …)
│       ├── queue.py          # `rero search queue` Celery queue commands
│       ├── task.py           # `rero search task` commands
│       └── snapshot/         # `rero search snapshot` commands
│           ├── cli.py        # snapshot create/list/delete/restore
│           ├── policy.py     # `rero search snapshot policy` Snapshot Management (SM) policies
│           └── repository.py # `rero search snapshot repository` commands
└── modules/
    ├── tasks.py              # run_on_worker Celery task
    ├── utils.py              # chunk() utility
    └── export/
        ├── ext.py            # ReroInvenioBaseExportApp Flask extension
        ├── views.py          # ExportResource view + create_blueprint_from_app
        └── config.py         # Export REST endpoint configuration
```

### Entry points

Registered in `pyproject.toml`:

| Entry point group | Name | Target |
|---|---|---|
| `flask.commands` | `rero` | `rero_invenio_base.cli:rero` |
| `invenio_base.apps` | `rero-invenio-base-export` | `ReroInvenioBaseExportApp` |
| `invenio_base.api_blueprints` | `rero_ils_exports` | `create_blueprint_from_app` |
| `invenio_celery.tasks` | `rero` | `rero_invenio_base.modules.tasks` |

### Export module

`ExportResource` is a `ContentNegotiatedMethodView` that streams record search results. Routes are registered dynamically from the `RERO_INVENIO_BASE_EXPORT_REST_ENDPOINTS` config key via `create_blueprint_from_app`. Each endpoint maps MIME types to serializers and prepends `/export` to the list route.

## Code style

- Be clear and concise in docstrings; do not over-comment the code.
- Do not use Python type annotations (no `-> str`, `: str`, etc. in signatures).
- Use **Sphinx-style** docstrings (`:param x:`, `:returns:`, `:rtype:`).
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org).

## Testing

- Tests use function-based style (no class-based tests).
- Test fixtures are in `tests/conftest.py`; sample data in `tests/data/`.
- `--doctest-modules` is active — doctests in module files are run by default.

### Running the tests (done by humans)

Human developers run tests from their consoles after starting the SEARCH container:

```bash
uv run ./scripts/test   # full suite (lint + pip-audit + pytest with SEARCH)
uv run pytest           # pytest only (SEARCH must already be running)
```
