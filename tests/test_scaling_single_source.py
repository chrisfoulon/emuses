"""Structural guards against the dead-route pattern that hid the scaling defect.

WHAT WENT WRONG, so this file is not tidied away as pedantry.

Three mechanisms existed for carrying the embedding scaling factors from the run that
trained a morphospace to whoever needed them later. Two of them did nothing:

  1. ``umap_model.min_embeddings_`` / ``max_embeddings_`` -- attributes read with
     ``getattr`` in ``inference_stage``. Nothing in ``emuses/`` has ever set them. The
     only assignment anywhere in the tree was on a ``Mock`` in
     ``tests/inference/test_normalization_validation.py``, so the route had a passing
     test and a ``None`` in production.
  2. Context keys ``embedding_train_min_coords`` / ``embedding_train_max_coords``,
     published by ``umap_stage`` and read by no stage. Asserted only in
     ``tests/inference/test_normalization_analysis.py``, against a context that test
     had built itself.

Only ``embedding_scaling.json`` was real.

**The pattern, which is the thing worth guarding:** a test that constructs its own input
can validate a *consumer* while no *producer* exists. It proves "if X were set we would
use it". It never proves "X is set". Prose review does not catch this -- the code reads
correctly at every individual site. A structural check does, which is why this repo
already uses AST assertions for this class of problem (``test_architecture_boundary.py``,
``test_pytest_option_registration.py``).

Full context: ``dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md`` and
ADR section 2.4b.

Everything here is AST-based, never substring matching. A comment or docstring naming a
banned attribute must not fail these tests -- this file and the ones it describes talk
about the dead names at length, and a grep-shaped guard would either forbid explaining
the bug or need an exclusion list that quietly grows until it excludes the bug.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DIR = PROJECT_ROOT / "emuses"
TESTS_DIR = PROJECT_ROOT / "tests"

PLAN_DOC = "dev-docs/methodology/embedding_scaling_and_boundary_bias_plan.md"

#: The attribute names of dead route 1. Trailing underscore is sklearn's "fitted
#: attribute" convention, which is exactly why they looked plausible.
BANNED_ATTRIBUTES = ("min_embeddings_", "max_embeddings_")

#: This file necessarily mentions the banned names as data. So does the module that
#: explains them. Excluded by path, not by pattern.
SELF = Path(__file__).resolve()


def _python_files(*roots):
    for root in roots:
        for path in sorted(root.rglob("*.py")):
            if path.resolve() == SELF:
                continue
            yield path


def _parse(path):
    try:
        return ast.parse(path.read_text(encoding="utf-8"), str(path))
    except (SyntaxError, UnicodeDecodeError) as exc:  # pragma: no cover - defensive
        pytest.fail(f"could not parse {path}: {exc}")


def _rel(path):
    try:
        return str(Path(path).resolve().relative_to(PROJECT_ROOT))
    except ValueError:  # pragma: no cover - defensive
        return str(path)


# ---------------------------------------------------------------------------
# Dead route 1: scaling factors as attributes on the UMAP model object
# ---------------------------------------------------------------------------


def test_scaling_is_not_carried_on_the_umap_model_object():
    """No code may set or read min_embeddings_ / max_embeddings_ on any object.

    Catches attribute access (``x.min_embeddings_``), assignment, and the string
    form used by ``getattr``/``setattr``/``hasattr`` -- the form the original defect
    actually used, and the one an attribute-only check would have missed.
    """
    offenders = []

    for path in _python_files(PACKAGE_DIR, TESTS_DIR):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute) and node.attr in BANNED_ATTRIBUTES:
                offenders.append(f"{_rel(path)}:{node.lineno}: .{node.attr}")
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in ("getattr", "setattr", "hasattr")
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and node.args[1].value in BANNED_ATTRIBUTES
            ):
                offenders.append(
                    f"{_rel(path)}:{node.lineno}: {node.func.id}(..., "
                    f"{node.args[1].value!r})"
                )

    assert not offenders, (
        "The embedding scaling factors are being carried on the UMAP model object "
        "again:\n  " + "\n  ".join(offenders) + "\n\n"
        "Nothing in emuses/ sets these attributes, so in production the read returns "
        "None and the rescale is silently skipped -- predictors fitted on rescaled "
        "coordinates then receive raw ones, and every prediction comes out nearly "
        "identical. A test can make this look alive by setting the attribute on a "
        "Mock; that proves the consumer works, never that a producer exists.\n\n"
        f"The factors have one home: embedding_scaling.json, written by UMAPStage and "
        f"read through emuses.tools.embedding_spaces.load_scaling(). See {PLAN_DOC}."
    )


def test_embedding_scaling_json_is_written_and_read_through_the_shared_module():
    """The one live route must stay a shared function, not be re-hand-rolled.

    There used to be three separate ``json.load`` copies of this parse in
    ``inference_stage`` alone, which is how one of them drifted onto a model
    attribute nobody sets. Assert the producer and the consumers reach the filename
    through ``embedding_spaces``.
    """
    from emuses.tools import embedding_spaces

    assert embedding_spaces.SCALING_FILENAME == "embedding_scaling.json"

    for module in ("emuses/pipelines/umap_stage.py", "emuses/pipelines/inference_stage.py"):
        tree = _parse(PROJECT_ROOT / module)
        imported = {
            alias.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
            and node.module == "emuses.tools.embedding_spaces"
            for alias in node.names
        }
        assert "SCALING_FILENAME" in imported, (
            f"{module} no longer imports SCALING_FILENAME from "
            f"emuses.tools.embedding_spaces. Spelling the filename literally in each "
            f"module is how the three copies of this parse drifted apart. See {PLAN_DOC}."
        )


# ---------------------------------------------------------------------------
# Dead route 2 (generalised): context keys written by a stage and read by nobody
# ---------------------------------------------------------------------------

#: Context keys that are written and never read, as of 2026-09-06. This is a record of
#: the tree's current state, not an endorsement: each of these is a candidate dead
#: route. They are NOT removed here because removal needs evidence this scan cannot
#: give (see the limitations note on the test below), and because a wholesale dead-code
#: sweep is planned separately.
#:
#: Do not add to this set to make a new failure go away. A key you just wrote and
#: nothing reads is the bug this file exists to catch.
KNOWN_UNREAD_CONTEXT_KEYS = frozenset(
    {
        "ae_loaded_from_disk",
        "ae_pretraining_results",
        "cluster_labels_path",
        "cluster_model_path",
        "embedding_test_coords",
        "embedding_train_cluster_labels",
        "embedding_train_clusterer",
        "embedding_train_coords",
        "model_path",
        "performance_summary",
        "prediction_X",
        "prediction_task",
        "prediction_y",
        "verify_integrity",
    }
)

#: The names the inter-stage dictionary goes by.
CONTEXT_NAMES = frozenset({"context", "ctx"})


def _scan_context_keys():
    """Return (writes, reads), each mapping a literal key to the sites that use it.

    LIMITATIONS, stated because a guard whose blind spots are undocumented is the
    thing it is guarding against:

    * **Literal string keys only.** ``context[some_variable]`` is invisible. Nothing
      in the tree does that today; if that changes, this scan silently weakens.
    * **Name-based.** Only dicts spelled ``context`` or ``ctx`` are seen.
    * ``**context`` splat and ``context.items()`` consumption would count as reads of
      every key. Neither occurs in ``emuses/`` today (the three ``.keys()`` uses are
      logging), so absence of a read here really is absence of a consumer.
    """
    writes, reads = {}, {}

    def note(store, key, path, lineno):
        store.setdefault(key, []).append(f"{_rel(path)}:{lineno}")

    for path in _python_files(PACKAGE_DIR):
        tree = _parse(path)
        for node in ast.walk(tree):
            # context["key"] = ...
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if (
                        isinstance(target, ast.Subscript)
                        and isinstance(target.value, ast.Name)
                        and target.value.id in CONTEXT_NAMES
                        and isinstance(target.slice, ast.Constant)
                        and isinstance(target.slice.value, str)
                    ):
                        note(writes, target.slice.value, path, target.lineno)

            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                func = node.func
                if isinstance(func.value, ast.Name) and func.value.id in CONTEXT_NAMES:
                    if func.attr == "update":
                        for arg in node.args:
                            if isinstance(arg, ast.Dict):
                                for key in arg.keys:
                                    if isinstance(key, ast.Constant) and isinstance(
                                        key.value, str
                                    ):
                                        note(writes, key.value, path, key.lineno)
                        for kw in node.keywords:
                            if kw.arg:
                                note(writes, kw.arg, path, node.lineno)
                    elif func.attr == "setdefault" and node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            note(writes, arg.value, path, node.lineno)
                    elif func.attr in ("get", "pop") and node.args:
                        arg = node.args[0]
                        if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                            note(reads, arg.value, path, node.lineno)

            # ... = context["key"]
            if (
                isinstance(node, ast.Subscript)
                and isinstance(node.value, ast.Name)
                and node.value.id in CONTEXT_NAMES
                and isinstance(node.slice, ast.Constant)
                and isinstance(node.slice.value, str)
                and isinstance(node.ctx, ast.Load)
            ):
                note(reads, node.slice.value, path, node.lineno)

            # "key" in context
            if (
                isinstance(node, ast.Compare)
                and len(node.ops) == 1
                and isinstance(node.ops[0], ast.In)
                and isinstance(node.comparators[0], ast.Name)
                and node.comparators[0].id in CONTEXT_NAMES
                and isinstance(node.left, ast.Constant)
                and isinstance(node.left.value, str)
            ):
                note(reads, node.left.value, path, node.lineno)

    return writes, reads


def test_the_two_scaling_context_keys_stay_gone():
    """The specific keys of dead route 2 must not come back.

    Separate from the general check below so that its failure names the actual
    history rather than appearing as one more entry in a list.
    """
    writes, reads = _scan_context_keys()
    resurrected = [
        f"{key} written at {', '.join(writes[key])}"
        for key in ("embedding_train_min_coords", "embedding_train_max_coords")
        if key in writes
    ]
    assert not resurrected, (
        "The scaling factors are being published on the pipeline context again:\n  "
        + "\n  ".join(resurrected)
        + "\n\nThese two keys existed for a long time with no production consumer, and "
        "looked wired because a test asserted on a context it had constructed itself. "
        "Downstream stages read embedding_scaling.json through "
        f"emuses.tools.embedding_spaces.load_scaling(). See {PLAN_DOC}."
    )


def test_no_new_write_only_context_keys():
    """Every context key a stage writes should be read by some stage.

    This is the general form of dead route 2, and it is the check that would have
    caught it without anyone knowing to look. Fourteen such keys already exist and are
    listed in KNOWN_UNREAD_CONTEXT_KEYS; this asserts the set does not grow, and
    notices when it shrinks so the list cannot go stale.
    """
    writes, reads = _scan_context_keys()
    unread = frozenset(writes) - frozenset(reads)

    new = sorted(unread - KNOWN_UNREAD_CONTEXT_KEYS)
    assert not new, (
        "These context keys are written and never read:\n  "
        + "\n  ".join(f"{key} written at {', '.join(writes[key])}" for key in new)
        + "\n\nA key nothing reads is a dead route: the producer looks correct, the "
        "value is real, and no consumer ever sees it. Either wire a consumer, or do "
        "not publish it. Do NOT add it to KNOWN_UNREAD_CONTEXT_KEYS -- that set records "
        f"pre-existing debt, not a place to file new debt. See {PLAN_DOC}."
    )

    fixed = sorted(KNOWN_UNREAD_CONTEXT_KEYS - unread)
    assert not fixed, (
        "These keys are listed in KNOWN_UNREAD_CONTEXT_KEYS but now have a reader (or "
        f"are no longer written): {', '.join(fixed)}. Remove them from that set so it "
        "keeps describing the tree. It is an inventory of known dead routes, and an "
        "inventory nobody prunes stops being evidence of anything."
    )
