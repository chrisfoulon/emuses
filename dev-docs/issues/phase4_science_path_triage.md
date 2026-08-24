# Phase 4 — the science-path test failures, triaged by root cause

_Measured 2026-08-24 on `feat/inference-on-service`:_
`pytest tests/pipelines tests/inference tests/flexible-inference-stage` → **33 failed, 155 passed**, 38 s.

The 33 are not 33 problems. They are seven causes, and five of them are one design change that the
tests never followed: **`InferenceStage._predict` returns per-target results
(`target_results[target]['ensemble_predictions']`), not a flat `ensemble_predictions`.** The same
defect family produced the empty HTTP responses fixed in Phase 1F.

## Clusters

| # | cause | tests | verdict |
|---|---|---|---|
| C1 | Patched `_predict` returns the pre-multi-target shape `{'predictions': [...]}`; the stage requires `target_results` → `KeyError: 'target_results'` at `inference_stage.py:778` | 5 (`test_inference_stage_progress.py`) | tests stale |
| C2 | A bare `MagicMock` model answers `hasattr(model, 'named_steps')` **True**, so the pipeline-component branch runs and every prediction is a `MagicMock` → empty ensemble, `unsupported format string passed to MagicMock.__format__` | 6 | tests over-mocked |
| C3 | Test asserts `ensemble_predictions` at the top level of `_predict`'s return | 3 | tests stale |
| C4 | `EMUSESPipeline(args, inference_data=...)` is **dead**: stored at `emuses_pipeline.py:47`, never read again | 6 (`test_pipeline_consolidation.py`) | code: remove dead parameter |
| C5 | Input normalization moved out of `InferenceStage._transform_features` into `EMUSESPipeline` (inference mode loads `input_scaler.joblib`, `emuses_pipeline.py:470`); tests still assert the stage normalizes | 9 | tests encode the superseded design |
| C6 | `_load_features_from_context` ignores `prediction_test_features` / `prediction_test_labels`, which `pipeline_runner.py:523` said it would read | 2 | **tests contradicted each other**; the refusal is correct — see below |
| C7 | `InferenceStage.output_path` is a `PosixPath`, so `model_info` is not JSON-serialisable | 1 | code: coerce to `str` |

## Production defects found while triaging (not test problems)

1. **Two result shapes still exist.** `_predict`'s "no prediction models" branch
   (`inference_stage.py:728`) returns the *old* flat shape, so a model folder without prediction
   models dies at `predictions['target_results']` with `KeyError` instead of the dummy result that
   branch claims to produce.
2. **A length mismatch of zero is not treated as an error.** `_calculate_validation_metrics`
   truncates to `min(len(pred), len(truth))`, logs "using first 0 samples", and then calls
   `np.min([])` → `zero-size array to reduction operation minimum`. The opaque numpy error is what a
   user sees when the ensemble came back empty.
3. **A log line reports a number it did not measure.** `Target {target} ensemble complete:
   {len(embeddings)} predictions generated` prints the *input* count. It said "5 predictions
   generated" while the ensemble was empty — the log actively hid C2.
4. **C6 above**: the aliasing the runner documents is done by `HeatmapStage` (`heatmap_stage.py:784`)
   rather than by the stage, so the stage's contract is narrower than its callers assume.

## The contradiction worth remembering (C6)

Two tests in the suite asserted opposite contracts and both had passed at some point:

- `test_semantic_aliasing.py` and `test_context_data_fix.py`: `prediction_test_features` has the
  **highest** priority in `_load_features_from_context`.
- `test_inference_stage_context_integration.py`: a context holding *only* those keys must **raise**.

The refusal is right, and not by a vote. `HeatmapStage` copies **either**
`prediction_test_features` **or** `prediction_train_features` into `inference_features`
(`heatmap_stage.py:784` and `:792`). If InferenceStage preferred the test split on its own, it would
silently override that choice and validate against data the stage upstream deliberately did not
select. The stage reads what it was handed; it does not re-decide the split. The comment in
`pipeline_runner.py` that said otherwise was corrected.

## Outcome

**33 failed / 155 passed → 185 passed, 0 failed** across the three directories
(`fix/science-path-tests`, commit `d147063`).

Five production fixes, seven perturbations run — the empty-model shape, the path coercion, the
zero-sample guard, the pipeline's scaler application, double normalization in the stage, the
handover-key priority, and the pipeline's `inference_features` key — each confirmed to fail exactly
the tests that claim to cover it, with the patch's application asserted before the run.

Two test files deleted: `tests/cli/test_inference_consolidation_simple.py` and
`tests/inference/test_inference_pipeline_fix.py`. Every test in them constructed the dead
`inference_data` parameter, and one called `load_and_process_inputs()`, a method that no longer
exists. Their invariants (context keys, no double processing) are asserted against the live path in
`tests/pipelines/test_inference_runner.py` and the rewritten
`tests/inference/test_pipeline_consolidation.py`.

### A trap this session paid for

`git checkout <file>` to undo a perturbation **also discards uncommitted work in that file**. Doing
it after a perturbation reverted nine production edits; the next three perturbation patches then
failed to apply, their `assert` fired unnoticed inside a shell heredoc, and the tests failed anyway —
for the missing work, not the perturbation. It read exactly like a successful perturbation. Commit
first, then perturb, and assert the patch applied *and* that the assertion is visible.

## Not in scope (recorded, per the standing decision)

`test_data/features.csv` is rank-1, so nothing here can assert prediction *quality* — only plumbing.

Also noticed, not acted on: `tests/pipelines/test_multi_target_end_to_end.py.backup` is checked in
next to the real file.
