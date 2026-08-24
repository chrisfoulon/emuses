"""The core/extras boundary, enforced.

EMUSES accumulated a large set of features that no entry point reaches: a model
marketplace (search, analytics, ranking, benchmarking, community management,
academic/GDPR compliance) and a multi-tenant service layer. On 2026-08-19 that
was measured at 16,585 LOC of production code and 645 test functions — 26% of
the suite — exercising code nothing runs.

Nothing was deleted. Those features are *parked*: kept in the tree, importable,
tested on demand via ``pytest -m extras``, but kept out of the default run and
out of the core's import graph. Since 2026-08-24 they also live in their own
package, ``emuses/extras/``, so which side of the line a module is on follows
from where its file sits.

This test is the mechanical backstop for that boundary. Prose in a README does
not survive nine months of sessions; a failing test does.

**The rule**: a core module must not import an extras module at module level.
Core *may* import extras lazily — inside a function, or behind
``try: ... except ImportError:`` — because that is how an optional feature is
meant to be wired. ``foundation_fastapi_service/app.py`` already does exactly
this for the multi-user endpoints, gated on ``is_service_mode_enabled()``.

If you are adding a feature and this test fails, the question to ask is not
"how do I silence it" but "is this feature core?". If it genuinely is, move the
file out of ``emuses/extras/`` deliberately and say why in
``.codebase-memory/adr.md``.
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
# imports", and the test could never fail. This is a product decision, now
# carried mostly by package layout rather than by a hand-kept list of names.

EXTRAS_PACKAGES = (
    # Auth, workspaces, quotas, multi-tenancy. Already gated at runtime by
    # DeploymentMode; this keeps it gated at import time too.
    "emuses.multi_user_service",
    # The marketplace (search, analytics, ranking, benchmarking, community,
    # compression, migration), the publication/GDPR compliance scaffolding, and
    # the cloud and database registry backends. Until 2026-08-24 these were 22
    # names listed one by one below, sitting in emuses/tools/ next to the code
    # that is core; the move gave them their own package so membership follows
    # from where a file lives rather than from a list someone must maintain.
    #
    # The *local* folder registry stayed in tools/ (local_model_registry,
    # model_io, base_model_registry, storage_manager, model_registry_factory,
    # model_registry_metrics, model_registry_health) — it is the model sharing
    # that is actually used.
    "emuses.extras",
)

# What did not fit the package split: two modules parked in place, because each
# sits inside a package that is otherwise core.
EXTRAS_MODULES = frozenset({
    # The CLI front end for cloud validation. Lives in cli/ with the live
    # commands, and is reachable only through the parked backend.
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
            # `from emuses.extras.model_cache import X` also yields the symbol,
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
            "move its file out of emuses/extras/ - recording why in "
            ".codebase-memory/adr.md.",
            pytrace=False,
        )


def test_the_checker_has_teeth():
    """A boundary test that cannot fail protects nothing.

    Guards against the checker silently degrading - e.g. if the guarded-import
    detection were widened until everything counted as guarded.
    """
    package = "emuses.pipelines"

    unguarded = "from emuses.extras.model_cache import ModelCache\n"
    assert "emuses.extras.model_cache" in unguarded_imports(unguarded, package)

    in_function = "def f():\n    from emuses.extras.model_cache import ModelCache\n"
    assert unguarded_imports(in_function, package) == set()

    behind_try = (
        "try:\n"
        "    from emuses.extras.model_cache import ModelCache\n"
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


def test_the_extras_package_is_actually_declared():
    """The 2026-08-24 move traded a list of names for a package.

    That is a better boundary only while the package is in EXTRAS_PACKAGES.
    Measured by removing the entry: the real core-to-extras import stops being
    reported, and in its place come ~15 violations from parked modules
    importing ``emuses.multi_user_service.models`` - legitimate extras-to-extras
    imports, now mis-read as core reaching into extras. So the failure is loud
    but points everywhere except at the cause, which is the kind of report
    people fix by loosening something. This names it instead.
    """
    package_dir = PACKAGE_ROOT / "extras"
    assert package_dir.is_dir(), "emuses/extras/ is gone; the move was undone"

    parked = sorted(
        p.stem for p in package_dir.glob("*.py") if p.stem != "__init__"
    )
    assert len(parked) > 15, (
        f"emuses/extras/ holds only {len(parked)} modules. If features were "
        "promoted to core that is fine - say why in .codebase-memory/adr.md "
        "and update this floor."
    )

    unclassified = [m for m in parked if not is_extras(f"emuses.extras.{m}")]
    assert not unclassified, (
        "emuses/extras/ modules are not being treated as extras: "
        f"{unclassified}. EXTRAS_PACKAGES has probably lost 'emuses.extras', "
        "which makes this whole check pass while enforcing nothing."
    )

    assert not is_extras("emuses.pipelines.umap_stage"), (
        "A core module classified as extras - EXTRAS_PACKAGES is too broad, "
        "and core-to-core imports would now be reported as violations."
    )
