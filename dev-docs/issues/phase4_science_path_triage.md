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
| C6 | `_load_features_from_context` ignores `prediction_test_features` / `prediction_test_labels`, which `pipeline_runner.py:523` says it will read | 2 | code gap (masked by HeatmapStage) |
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

## Not in scope (recorded, per the standing decision)

`test_data/features.csv` is rank-1, so nothing here can assert prediction *quality* — only plumbing.
