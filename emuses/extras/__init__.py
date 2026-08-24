"""Parked features: kept, importable, tested on demand — outside the core.

These modules are a real body of work that no EMUSES entry point reaches: the
model marketplace (search, analytics, ranking, benchmarking, community,
compression, migration), the publication and GDPR compliance scaffolding for a
public registry, and the cloud and database registry backends. Measured on
2026-08-19 at 16,585 LOC with 1,071 of 2,499 tests exercising it, for a registry
that holds one model.

Nothing here was deleted, because none of it is *wrong* — it is unfinished. It
lives in its own package so the boundary is structural rather than a list
somebody has to remember to maintain: core imports ``emuses.tools``, extras
import ``emuses.extras``, and ``tests/test_architecture_boundary.py`` fails if
core reaches in here at module level.

Extras may import core freely. Core may reach the other way only *lazily* —
inside a function, or behind ``try/except ImportError`` — which is how an
optional backend is meant to be wired; ``emuses.tools.model_registry_factory``
loads the cloud and database registries exactly that way.

Their tests live in ``tests/extras/`` and are deselected from the default run by
``-m "not extras"``. Run them with ``pytest -m extras``.

See ``.codebase-memory/adr.md`` §2.10.
"""
