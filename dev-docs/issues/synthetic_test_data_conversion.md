# Unfinished: synthetic → real test data conversion (former "Phase 3")

**Status**: Open, dormant since 2025-09. Low priority — no known incorrect behaviour depends on it.
**Logged**: 2026-07-30, during the LAD v2 migration.

## What this is

A test-quality effort ran in 2025-08/09 and completed two phases:

- **Phase 1** — systematised the test-quality methodology.
- **Phase 2** — converted InferenceStage tests from synthetic to real data, taking that suite from
  8/18 passing to 15/18 (44% → 83%).

**Phase 3** was planned but never executed: extend the same conversion across the rest of the
codebase. The handover set the target at ~31 test files and ~275 `np.random.rand()` instances.

## Current state

As of 2026-07-30, **208 `np.random.rand()` instances remain across 27 test files**. Compared with the
~275/31 recorded in the handover, some conversion happened after Phase 2 and then stopped. Nobody has
picked it up in the ~11 months since.

Measure the current figure with:

```bash
grep -rIo "np.random.rand" tests/ | wc -l    # instances
grep -rIl "np.random.rand" tests/ | wc -l    # files
```

## Why it may still be worth doing

The Phase 2 result is the argument for it: those tests were not failing because the code was broken,
they were failing because synthetic random data produced shapes and distributions the pipeline never
encounters in practice. The same false-failure pattern likely sits in the remaining 27 files.

The counter-argument is that 11 months of dormancy without pain suggests the remaining instances are
in tests where synthetic data is harmless (utilities, edge cases) rather than in pipeline paths.
**Triage before converting in bulk** — target integration and pipeline tests, skip utility tests where
random input is genuinely appropriate.

## How

Conversion pattern and the 30/20 split convention: `dev-docs/test_quality_conventions.md`.
Full historical context: `dev-docs/project-history/phase-implementations/test_quality_phase2_to_phase3_handover.md`.
Regression gate between batches: `python scripts/dev_test_runner.py` (13/13).
