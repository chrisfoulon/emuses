"""The core/extras boundary, enforced.

EMUSES accumulated a large set of features that no entry point reaches: a model
marketplace (search, analytics, ranking, benchmarking, community management,
academic/GDPR compliance) and a multi-tenant service layer. On 2026-08-19 that
was measured at 16,585 LOC of production code and 645 test functions — 26% of
the suite — exercising code nothing runs.

Nothing was deleted. Those features are *parked*: kept in the tree, importable,
tested on demand via ``pytest -m extras``, but kept out of the default run and
out of the core's import graph.

This test is the mechanical backstop for that boundary. Prose in a README does
not survive nine months of sessions; a failing test does.

**The rule**: a core module must not import an extras module at module level.
Core *may* import extras lazily — inside a function, or behind
``try: ... except ImportError:`` — because that is how an optional feature is
meant to be wired. ``foundation_fastapi_service/app.py`` already does exactly
this for the multi-user endpoints, gated on ``is_service_mode_enabled()``.

If you are adding a feature and this test fails, the question to ask is not
"how do I silence it" but "is this feature core?". If it genuinely is, move it
out of EXTRAS deliberately and say why in ``.codebase-memory/adr.md``.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_ROOT = PROJECT_ROOT / "emuses"

# --- The boundary, declared by intent rather than derived from the graph ------
#
# Deriving it from reachability would be circular: core would be "whatever core
# imports", and the test could never fail. This list is a product decision.

EXTRAS_PACKAGES = (
    # Auth, workspaces, quotas, multi-tenancy. Already gated at runtime by
    # DeploymentMode; this keeps it gated at import time too.
    "emuses.multi_user_service",
    # Populated by the Phase 2 move; harmless until then.
    "emuses.extras",
)

EXTRAS_MODULES = frozenset({
    # Marketplace: search, analytics, ranking, benchmarking, community.
    "emuses.tools.advanced_search",
    "emuses.tools.model_analytics",
    "emuses.tools.model_benchmarking",
    "emuses.tools.model_cache",
    "emuses.tools.personalized_ranking",
    "emuses.tools.community_model_manager",
    "emuses.tools.streaming_analytics",
    "emuses.tools.usage_alerts",
    "emuses.tools.model_compression",
    "emuses.tools.model_migration",
    "emuses.tools.registry_config",
    # Publication/compliance scaffolding for a public registry.
    "emuses.tools.academic_features",
    "emuses.tools.academic_compliance",
    "emuses.tools.gdpr_compliance",
    # Cloud and database registry backends. The *local* folder registry
    # (local_model_registry, model_io, base_model_registry, storage_manager,
    # model_registry_factory, model_registry_metrics) is core — it is the model
    # sharing that is actually used.
    "emuses.tools.cloud_model_registry",
    "emuses.tools.cloud_storage",
    "emuses.tools.cloud_resilience",
    "emuses.tools.cloud_validation",
    "emuses.tools.database_model_registry",
    "emuses.tools.database_index_optimizer",
    "emuses.tools.model_permission_manager",
    "emuses.tools.model_registry_cache",
    "emuses.cli.cloud_validation",
    # Orphaned inside an otherwise-live service: referenced only by its own test.
    "emuses.foundation_fastapi_service.stage_runners",
})


def _module_name(path: Path) -> str:
    rel = path.relative_to(PROJECT_ROOT).with_suffix("")
    name = ".".join(rel.parts)
    return name[: -len(".__init__")] if name.endswith(".__init__") else name


def _iter_modules():
    for path in sorted(PACKAGE_ROOT.rglob("*.py")):
        parts = set(path.parts)
        if "__pycache__" in parts or any(p.startswith("_archive") for p in parts):
            continue
        yield _module_name(path), path


def is_extras(module: str) -> bool:
    return module in EXTRAS_MODULES or any(
        module == pkg or module.startswith(pkg + ".") for pkg in EXTRAS_PACKAGES
    )


def unguarded_imports(source: str, package: str) -> set[str]:
    """emuses.* imported at module level, not lazily and not behind ImportError.

    An import is treated as guarded when it sits inside a function body, or
    inside the ``try`` of a ``try/except ImportError`` (or bare ``except``).
    Those are the deliberate ways to wire an optional dependency.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    guarded: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            guarded.update(id(child) for child in ast.walk(node))
        elif isinstance(node, ast.Try):
            catches_import = any(
                handler.type is None or "ImportError" in ast.dump(handler.type)
                for handler in node.handlers
            )
            if catches_import:
                for stmt in node.body:
                    guarded.update(id(child) for child in ast.walk(stmt))

    found: set[str] = set()
    for node in ast.walk(tree):
        if id(node) in guarded:
            continue
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                if node.level > 1:
                    base = base[: len(base) - (node.level - 1)]
                found.add(".".join(base + ([node.module] if node.module else [])))
            else:
                found.add(node.module or "")
    return {name for name in found if name.startswith("emuses")}


def _violations():
    out = []
    for module, path in _iter_modules():
        if is_extras(module):
            continue
        package = module.rsplit(".", 1)[0] if "." in module else module
        for imported in unguarded_imports(
            path.read_text(encoding="utf-8", errors="ignore"), package
        ):
            # `from emuses.tools.model_cache import X` also yields the symbol,
            # so check the parent module too.
            for candidate in (imported, imported.rsplit(".", 1)[0]):
                if is_extras(candidate):
                    out.append((module, candidate))
                    break
    return sorted(set(out))


def test_core_does_not_import_extras_at_module_level():
    violations = _violations()
    if violations:
        lines = "\n".join(f"  {core}  ->  {extra}" for core, extra in violations)
        pytest.fail(
            "Core modules import parked (extras) modules at module level:\n"
            f"{lines}\n\n"
            "Either import it lazily (inside a function, or behind "
            "try/except ImportError, as foundation_fastapi_service/app.py does "
            "for the multi-user endpoints), or decide the feature is core and "
            "remove it from EXTRAS in this file - recording why in "
            ".codebase-memory/adr.md.",
            pytrace=False,
        )


def test_the_checker_has_teeth():
    """A boundary test that cannot fail protects nothing.

    Guards against the checker silently degrading - e.g. if the guarded-import
    detection were widened until everything counted as guarded.
    """
    package = "emuses.pipelines"

    unguarded = "from emuses.tools.model_cache import ModelCache\n"
    assert "emuses.tools.model_cache" in unguarded_imports(unguarded, package)

    in_function = "def f():\n    from emuses.tools.model_cache import ModelCache\n"
    assert unguarded_imports(in_function, package) == set()

    behind_try = (
        "try:\n"
        "    from emuses.tools.model_cache import ModelCache\n"
        "except ImportError:\n"
        "    ModelCache = None\n"
    )
    assert unguarded_imports(behind_try, package) == set()


def test_boundary_lists_describe_modules_that_exist():
    """Stops the lists rotting into a set of names that no longer match files."""
    known = {module for module, _ in _iter_modules()}
    missing = sorted(m for m in EXTRAS_MODULES if m not in known)
    assert not missing, (
        f"EXTRAS_MODULES names modules that no longer exist: {missing}. "
        "Remove them, or fix the path if the module moved."
    )
