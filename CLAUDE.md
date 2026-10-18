# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

`uberpy` is a thin, synchronous wrapper around the Uber Direct (DaaS) API, built on `requests` + Pydantic v2. Python >= 3.13 (uses PEP 695 `type` aliases). Managed with `uv`, built with hatchling, `src/` layout.

## Commands

```sh
uv sync                                    # install deps (incl. dev group)
uv run --no-sync pytest                    # all tests
uv run --no-sync pytest tests/test_fields/test_structured_address.py::test_structured_address  # single test
uv run --no-sync ruff format src tests     # format (run after every Python edit)
uv run --no-sync ruff check .              # lint
uv run --no-sync mypy src                  # type check (currently reports missing `types-requests` stubs)
```

Pytest runs with `--import-mode=importlib`, so test modules are imported as `uberpy`/`tests` packages rather than by path.

## Architecture

**Client layer (`src/uberpy/core/`)**
- `Base` (`core/base.py`) owns all HTTP behavior: URL building (`https://api.uber.com/{version}/customers/{customer_id}/...`, path segments passed as varargs and URL-quoted), bearer auth, Pydantic body serialization (`model_dump(mode='json', exclude_none=True)`), and retries with exponential backoff + jitter (honors `Retry-After`) on retriable status codes and connection errors. Subclasses call `self._get/_post/_put/_patch/_delete(body, *path_segments)` and return `Model.model_validate(response)`.
- `Base.get_access_token(client_id=..., client_secret=...)` is a static helper for the OAuth client-credentials flow; the client accepts `access_token` as a string or as a callable returning one, which is called on every request (including retries) so a rotated token is picked up without a new client. An optional `refresh_access_token` callable is called on the first 401 of a call, and the request is retried right away with the token it returns, so a cached token that was rotated or revoked does not fail the call.
- Each API area is a `Base` subclass (`Quotes`, `Deliveries`). `UberDirect` (`core/uberdirect.py`) is the public entry point: it constructs every resource client with the same kwargs and a shared `requests.Session`, exposing them as attributes (`client.quotes`, `client.deliveries`). Adding a new resource means creating a `Base` subclass and wiring it into `UberDirect.__init__`.

**Models (`src/uberpy/models/`)** — request/response Pydantic models, one module per API area, all re-exported from `models/__init__.py`. They inherit `models.base.BaseModel` (camelCase alias generator, `validate_by_name`/`validate_by_alias`, `extra='ignore'`, `use_enum_values`). Fields are documented with a docstring directly below each attribute, mirroring the Uber API reference. Note that serialization in `Base._request` does not use `by_alias`, so request bodies go out with snake_case field names.

**Enums (`src/uberpy/constants/`)** — API enum values, re-exported from `constants/__init__.py`.

**Custom field types (`src/uberpy/fields.py`)** — reusable `Annotated` types encoding Uber-specific wire formats and rules:
- `StructuredAddress`: a TypedDict that Uber expects as a JSON *string*; accepts dict or JSON string, serializes to compact sorted JSON.
- `DecimalFromInt`: money as integer cents on the wire, `Decimal` in Python.
- `PhoneNumber`: E.164, default region `MX`.
- `PickupDeadlineDt` / `DropoffReadyDt` / `DropoffDeadlineDt`: `AfterValidator`s that cross-check time windows against previously validated fields via `info.data` — so **field declaration order in models matters** (`pickup_ready_dt` → `pickup_deadline_dt` → `dropoff_ready_dt` → `dropoff_deadline_dt`).

**Public API** — `uberpy/__init__.py` exports `UberDirect` plus the `constants`, `fields`, and `models` modules; consumers use `uberpy.models.X`, not deep imports. New models/enums must be added to the relevant `__init__.py`.

## Conventions

- All client constructor params are keyword-only; methods use `/` for path IDs (e.g. `delivery_id`) and `*` for `request=` models.
