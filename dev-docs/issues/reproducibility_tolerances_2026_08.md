# Run-to-run variation, measured — and the source that survived Phase 1D

_Measured 2026-08-23 on `chore/core-boundary`, after the seed wiring landed
(`687f7a9`, `4152635`). Harness: `scripts/measure_reproducibility.py`._

## Summary

Phase 1D made the **prediction** path reproducible. It did not make the whole
pipeline reproducible, and the config the test suite uses cannot show that,
because it has nothing to search.

**One source of run-to-run variation remains: `optuna.study.optimize(n_jobs>1)`.**
It is not float non-associativity, and no seed fixes it. Optuna's parallel mode
runs trials concurrently, so TPE's suggestion depends on which trials have
finished when each one asks — thread timing. The sampler is correctly seeded
(`UMAP_utils.py:633`); that is not enough.

Two arms differing in exactly one variable:

| arm | `umap_jobs` / `hdbscan_jobs` | metrics identical across 3 repeats at seed 42 |
|---|---|---|
| `midbudget` | 4 | **10 of 20** |
| `midbudget-serial` | 1 | **20 of 20** |

This matters for **Phase 1B2**. Today the CLI forks a service, `is_subprocess_context()`
is True and `get_safe_n_jobs()` clamps jobs to 1 — which is why CLI runs are
reproducible today, by accident rather than design. Moving execution in-process
turns that clamp off and would make CLI runs nondeterministic. Do not land 1B2
without deciding what to do about this.

## What was measured

Config under test is the `emuses_pipeline_results` fixture (`tests/conftest.py`),
because that is what Phase 3 pins: `umap_trials=1`, `hdbscan_trials=1`,
`optuna_trials=2`, `outer_folds=5`, `n_jobs=4`, `umap_jobs=4`, `hdbscan_jobs=4`,
`random_state=42`, `optim_dict_hcp` / `quick_train_dict`, Python API, on
`test_data` (48 samples × 7 features, 40 after the 0.8 split).

The harness parses `conftest.py` and refuses to run if its own config has drifted
from the fixture, since numbers measured on a different config would not apply to
what Phase 3 pins.

Metrics compared per run: composite score and the UMAP/HDBSCAN metrics from
`best_trial_info.json`; cluster count and noise fraction from `cluster_labels.npy`;
cluster structure by **adjusted Rand index** (ids are arbitrary); embedding
geometry by **pairwise-distance correlation** (UMAP is defined only up to rotation
and reflection); and every field of the prediction summary CSVs.

### Reproducibility at a fixed seed

| arm | runs | result |
|---|---|---|
| `fixture` / regression | 3 | 20/20 identical |
| `fixture` / multi_target_regression | 3 | 28/28 identical |
| `njobs` (`n_jobs` 1 vs 4) | 4 | 20/20 identical |
| `coredist` (`hdbscan_core_dist_n_jobs` 1 vs −1) | 4 | 20/20 identical |
| `midbudget` (`optim_dict_default`, 10/5/15) | 3 | **10/20 identical** |
| `midbudget-serial` (as above, jobs=1) | 3 | 20/20 identical |

**`hdbscan_core_dist_n_jobs` is exonerated.** It was the leading suspect
(parallel core-distance reductions are not float-associative). It changed
nothing — but the first measurement ran at a config where HDBSCAN returns zero
clusters with all 40 points labelled noise, leaving very little for a
reduction-order difference to change. That was recorded as weak evidence and
**re-measured on 2026-08-23** at the regression config, which produces 3 clusters
at `noise_fraction` 0.1:

| arm | runs | result |
|---|---|---|
| `regression-coredist` (1 vs −1, 3 real clusters) | 4 | 20/20 identical |

`composite_score` was 0.491357 in all four. The caveat is now closed: this is a
clean bill of health, not an artefact of a degenerate clustering.

`n_jobs` (model training) also changed nothing. That is a stronger result: those
runs did produce varying prediction scores across seeds, so the metric was live.

### What varies at the mid budget, same seed

`composite_score` 0.4154 / 0.4700 / 0.5004 (18% spread) · `n_clusters` 2 / 2 / 3 ·
cluster ARI vs first 1.0 / 0.794 · best `trial_number` 0 / 5 / 5 · embedding
distance correlation 0.77 / 0.54.

Prediction scores were identical across those three runs — the surviving
nondeterminism is in the search, not the prediction fit.

### Seed sensitivity

Three different master seeds, fixture budget:

| metric | seed 42 | seed 7 | seed 1234 |
|---|---|---|---|
| `composite_score` | 0.1565 | 0.3420 | 0.1455 |
| `n_clusters` | 0 | 2 | 0 |
| `noise_fraction` | 1.00 | 0.175 | 1.00 |
| `Mean_Score` | −0.4762 | −1.0045 | −0.1060 |
| `Min_Score` | −0.9809 | −2.4665 | −0.2388 |

Cluster ARI between seed 42 and seed 7 is **0.0**; embedding distance correlation
is **0.066**. The seed decides whether you get two clusters or none.

At the mid budget the spread narrows but does not close: `composite_score` 0.417 /
0.388 / 0.448, `n_clusters` 5 / 2 / 3.

**Read this correctly.** It is not a defect — it is what an under-converged search
on 40 samples looks like, and Phase 1D is what makes it visible: once every run at
a given seed agrees, the disagreement *between* seeds is the whole story. The
regression tolerances below are therefore tolerances for **detecting code changes
at a fixed seed**, and say nothing about scientific stability.

## Two traps found while measuring

**1. `optim_dict_hcp` does not search.** Every UMAP and HDBSCAN parameter in it is
fixed, and `UMAP_utils.py:430` deliberately collapses to a single trial when that
is true ("All parameters are fixed – running a single trial"). Raising
`umap_trials` against it changes nothing. A first version of the mid-budget arm
did exactly that and appeared to show that budget does not affect clustering; it
was measuring the prediction budget alone. Dicts that actually search:
`optim_dict_default`, `optim_dict_range`, `optim_dict_hard`,
`optim_dict_disconnectome`. Fixed: `optim_dict_hcp`, `optim_dict_test`.

**2. `noise_ratio` in `best_trial_info.json` holds `1 − noise_ratio`.**
`compute_noise_ratio` (`clustering_utils.py:53`) defaults to `normalized=True` and
returns `1 - raw`, so **`"noise_ratio": 0.0` means every point is noise**, not
none. Confirmed against `cluster_labels.npy`: 40 values, all −1, recorded as
`noise_ratio: 0.0`. This is a published artefact field and it reads as its own
opposite. Renaming it would break comparison with existing runs, so it is recorded
here rather than changed unilaterally.

## The PCA seeding fix, now verified empirically

Phase 1D item 4 seeded `PCAGWD` / `KernelPCAGWD` on the argument that
`svd_solver="auto"` switches to the randomized solver above
`max(X.shape) > 500`. That was verified structurally, because `test_data` is too
small to show it. Reproduced directly (sklearn 1.7.2):

| n | solver selected | two **unseeded** fits agree | two **seeded** fits agree |
|---|---|---|---|
| 50 | `full` | yes | yes |
| 600 | `randomized` | **no**, max diff 2.2e-10 | yes |
| 1437 | `randomized` | **no**, max diff 2.5e-08 | yes |

The defect was real and appears exactly at the predicted threshold. The magnitude
is small; the point is that it is nonzero, inside a nested CV that selects
hyperparameters on the result. Guarded by
`tests/test_seed_wiring.py::test_pca_nondeterminism_is_real_above_sklearn_threshold`,
which fails if sklearn changes its solver selection rather than silently passing.

Note for anyone re-checking: sklearn 1.7's `PCA` has **no** `svd_solver_`
attribute (the private `_fit_svd_solver` holds the choice). Assert on behaviour.

## Proposed tolerances for Phase 3

Local run-to-run variation at the fixture config is **exactly zero** on every
metric. Tolerances cannot be zero anyway: the suite runs in CI on different
hardware and ADR §2.9b puts bitwise-across-platforms out of scope. Every number
below is therefore labelled.

| what | tolerance | basis |
|---|---|---|
| prediction scores (`Mean_Score` etc.) | `rtol=1e-3` | **chosen** — CSVs are written to 4 dp, so 1e-3 is roughly the recorded precision |
| `composite_score`, UMAP/HDBSCAN metrics | `rtol=1e-6` | **chosen** — cross-BLAS allowance; measured variation is 0 |
| embedding pairwise-distance correlation | `>= 0.999` | **chosen** — measured 1.0 |
| cluster count | exact | **measured** — 0 variation, and an integer has no float drift |
| cluster ARI vs baseline | `>= 0.95` | **chosen** — measured 1.0 |

**Do not pin cluster structure from the fixture config.** It yields zero clusters
with everything labelled noise, so an ARI between two baselines is 1.0 by
construction and would never fail. `tests/regression/` therefore has its own
config (`regression_config.py`), the `midbudget-serial` arm, which produces 3
clusters at `noise_fraction` 0.1.

**These tolerances were proven to fail.** A one-line change to production code
(`UMAP_utils`, model seed shifted by one, no config touched) failed the composite
score, the cluster structure and the embedding geometry — while **prediction
scores and cluster count did not move**. Pinning only "the number that matters"
would have missed a real change to the science. See `tests/regression/README.md`.

## What was done about it

- **`umap_jobs`/`hdbscan_jobs` default to 1** (`bec42c9`). Reproducibility beats
  parallel search for a tool people publish from; parallel stays an opt-in that
  warns it forfeits reproducibility. That commit also found that `umap_jobs` was
  already serial *by accident* (a `None -> 1` mapping inside `UMAPStage`, declared
  nowhere), that `hdbscan_jobs` is inert entirely, and that `--help` was telling
  users a seed forces `n_jobs` to 1 — the exact claim measured false above.
- **`hdbscan_core_dist_n_jobs` re-measured** on a clustering config, above. Closed.
- **The regression suite got a config that actually clusters**: `tests/regression/`
  pins the `midbudget-serial` arm, and `test_baseline_is_not_degenerate` fails if
  it ever drifts back to an all-noise labelling where an ARI assertion cannot fail.

## CLI vs Python API, measured (2026-08-23, Phase 1B2)

Phase 1B2 moved local CLI execution in-process, which removes the fork and with it
the `get_safe_n_jobs()` clamp. The clamp is real and was measured directly:

| context | `is_subprocess_context()` | `get_safe_n_jobs(4)` |
|---|---|---|
| main process (in-process CLI, Python API) | False | 4 |
| `multiprocessing.Process` child (forked service) | True | **1** |

So `--n_jobs` was **inert on the CLI** and worked normally through the API. Removing
the fork changes it from 1 to whatever was asked for.

**Measured before the change shipped**, at the regression config
(`optim_dict_default`, 10/5/15 trials, `umap_jobs=1`, `hdbscan_jobs=1`, `n_jobs=4`,
seed 42, `test_size=0.2`), one variable at a time:

| comparison | scalar metrics identical | cluster ARI | distance corr |
|---|---|---|---|
| CLI forked (`n_jobs` clamped to 1) vs API baseline (`n_jobs=4`) | 18 / 18 | — | — |
| CLI in-process (`n_jobs=4`) vs CLI forked | 18 / 18 | 1.0 | 1.0 |
| CLI in-process vs API baseline | 18 / 18 | — | — |

Two things follow. The **CLI and Python API agree exactly**, so the two paths have not
silently diverged — the check Phase 1B was waiting on. And **`n_jobs` does not affect
the numbers** on this config, now confirmed on the CLI-vs-API axis as well as within
the API, so un-clamping it was safe.

Caveat, stated rather than assumed: this is 48 samples. `n_jobs` parallelises
independent work with order preserved on this path, but a config that reduces across
workers differently at larger n is not covered by this measurement.

Still open:

- Nothing from Phase 1B2. The clamp is gone and its removal is measured.
