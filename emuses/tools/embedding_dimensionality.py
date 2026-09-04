"""Decide, at configuration time, whether the enabled stages can consume the
embedding the UMAP search is allowed to produce.

Why this exists
---------------
UMAP is dimension-agnostic, and so is the prediction search: it fits against
embedding coordinates of any width. The **heatmap is not**. ``GridCreator`` and
``CorrelationGridCreator`` build a ``grid_size x grid_size`` mesh over exactly
two axes and raise ``ValueError`` on anything else
(``grid_creator.py:68``, ``correlation_grid_creator.py:243``).

That refusal is correct, but on its own it is close to useless:

* it fires **per target**, after UMAP training *and* the full nested-CV search
  (``heatmap_stage.py:1166``), so on ``DSD_repro`` it would arrive ~19 hours in;
* both call sites catch bare ``Exception`` and merely log
  (``heatmap_stage.py:1209``, ``:1261``), so the run **completes with exit 0**
  and no heatmaps, announced only by error lines inside a multi-MB log.

A run that looks successful and silently dropped its main output is the failure
mode this project keeps paying for. This module moves the decision to before
anything is trained, so an unsupported combination is refused in seconds with a
message that says what to do instead.

What is deliberately allowed
----------------------------
An N-D morphospace on its own is useful and is **not** blocked: ``emuses umap``
builds and saves it, and nothing downstream of that stage requires 2-D. Only a
run that would also produce heatmaps is refused.

Do not "fix" a refusal by loosening the grid check
--------------------------------------------------
Making the heatmap N-D is a design question, not a validation to relax. Two
measured reasons (2026-09-04):

* The adaptive grid in ``emuses_utils.compute_discrete_space`` is genuinely
  N-D generic, but its sizing criterion is point overlap, and 133 points in a
  10-D cube essentially never collide -- so it settles on **2 bins per axis**.
  It degrades to a useless resolution rather than exploding. (That code is also
  currently unreachable: ``DiscreteLatentSpace`` is never instantiated.)
* Clustering in N-D and projecting to 2-D for display would put genuinely
  separate clusters on top of each other, so the heatmap would no longer
  explain the prediction it sits next to.

Background and the evidence that 2-D is not the binding constraint on this
data: ``dev-docs/methodology/external_evidence_dsd.md`` section 7.2.
"""

from typing import Any, Dict, Iterable, Optional, Set

# The width every current heatmap consumer requires.
HEATMAP_N_COMPONENTS = 2

# Stage names (as used in pipeline_runner's `enabled_stages`) that cannot
# consume an embedding wider than HEATMAP_N_COMPONENTS.
STAGES_REQUIRING_2D = ("heatmap",)

# Upper bound when expanding a {"low": .., "high": ..} search range. A range is
# a declaration of intent, and any value in it can be chosen; we only need to
# know whether *some* choice is unsupported, so a wide range is capped rather
# than materialised.
_MAX_RANGE_EXPANSION = 64


class EmbeddingDimensionalityError(ValueError):
    """An enabled stage cannot consume the embedding width that was configured.

    Raised before any training starts. Carries the offending values so callers
    can report them without re-deriving.
    """

    def __init__(self, message: str, *, declared: Set[int], blocking_stages: tuple):
        super().__init__(message)
        self.declared = declared
        self.blocking_stages = blocking_stages


def _spec_to_values(spec: Any) -> Optional[Set[int]]:
    """Every value an Optuna parameter spec could resolve to.

    Mirrors the four forms `optim_utils.suggest_one` accepts. Returns None when
    the spec is a form this function does not understand -- an unknown spec must
    not be silently treated as "fine", but it is also not this module's job to
    reject a config `suggest_one` would have accepted.
    """
    if spec is None:
        return None
    if isinstance(spec, bool):  # bool is an int subclass; never a dimension
        return None
    if isinstance(spec, int):
        return {spec}
    if not isinstance(spec, dict):
        return None

    if "value" in spec:
        value = spec["value"]
        return {int(value)} if isinstance(value, int) and not isinstance(value, bool) else None

    if "choices" in spec:
        choices = spec["choices"]
        if isinstance(choices, (list, tuple)) and choices:
            values = {c for c in choices if isinstance(c, int) and not isinstance(c, bool)}
            return values or None
        return None

    if "low" in spec and "high" in spec:
        low, high = spec["low"], spec["high"]
        if not (isinstance(low, int) and isinstance(high, int)):
            return None
        step = spec.get("step") or 1
        if not isinstance(step, int) or step < 1:
            step = 1
        if high < low:
            return None
        if (high - low) // step + 1 > _MAX_RANGE_EXPANSION:
            # Too wide to enumerate; report the endpoints, which is enough to
            # decide whether an unsupported width is reachable.
            return {low, high}
        return set(range(low, high + 1, step))

    return None


def declared_n_components(optim_dict: Optional[Dict]) -> Optional[Set[int]]:
    """Every embedding width the UMAP search could choose, or None if unknown.

    None means "not declared" -- the caller should fall back to UMAP's own
    default rather than assume anything. `inputs_utils.py:769` uses
    ``umap_params.get("n_components", 2)``, so the effective default is 2.
    """
    if not isinstance(optim_dict, dict):
        return None
    umap_params = optim_dict.get("param", {}).get("umap", {})
    if not isinstance(umap_params, dict):
        return None
    return _spec_to_values(umap_params.get("n_components"))


def check_embedding_dimensionality(
    optim_dict: Optional[Dict],
    enabled_stages: Iterable[str],
    *,
    optim_dict_name: Optional[str] = None,
) -> Optional[Set[int]]:
    """Refuse a configuration whose embedding width no enabled stage can use.

    Returns the declared widths (or None if undeclared) so the caller can log
    what was accepted. Raises `EmbeddingDimensionalityError` when a stage in
    `STAGES_REQUIRING_2D` is enabled and the search could produce anything other
    than `HEATMAP_N_COMPONENTS`.

    A UMAP-only run is never refused: an N-D morphospace is a supported output.
    """
    declared = declared_n_components(optim_dict)
    if declared is None:
        # Undeclared resolves to UMAP's default of 2, which every stage supports.
        return None

    unsupported = sorted(v for v in declared if v != HEATMAP_N_COMPONENTS)
    if not unsupported:
        return declared

    stages = tuple(enabled_stages)
    blocking = tuple(s for s in STAGES_REQUIRING_2D if s in stages)
    if not blocking:
        # N-D with no 2-D-only stage enabled: allowed, and the caller logs it.
        return declared

    source = f" in optim_dict '{optim_dict_name}'" if optim_dict_name else ""
    widths = ", ".join(str(v) for v in sorted(declared))
    raise EmbeddingDimensionalityError(
        f"UMAP is configured{source} to produce an embedding of "
        f"n_components={widths}, but the enabled stage(s) "
        f"{', '.join(blocking)} require exactly {HEATMAP_N_COMPONENTS}.\n"
        f"\n"
        f"The heatmap builds a 2-D grid over the morphospace (GridCreator, "
        f"CorrelationGridCreator); it has no N-D form yet. This is refused now, "
        f"before training, because the grid would otherwise fail per target "
        f"AFTER the full search and the run would still exit 0 with no heatmaps.\n"
        f"\n"
        f"What works today:\n"
        f"  - Build the N-D morphospace on its own:  emuses umap ...\n"
        f"    (UMAP, HDBSCAN, embeddings and cluster labels are all saved, and "
        f"none of them require 2-D.)\n"
        f"  - Keep the heatmap: set n_components to {HEATMAP_N_COMPONENTS} in "
        f"the optim_dict and rerun.\n"
        f"\n"
        f"Making the heatmap N-D is an open design decision, not a check to "
        f"loosen -- see dev-docs/methodology/external_evidence_dsd.md section 7.2.",
        declared=set(declared),
        blocking_stages=blocking,
    )
