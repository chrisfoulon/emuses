# Numerical regression suite

Fails when a code change moves a scientific result. That is its only job.

```bash
pytest tests/regression -q          # ~128 s: one pipeline run per dataset
```

Three datasets. Two of them (`regression`, `multi_target_regression`) are 40-sample
fixtures that pin the **raw-derived** quantities — embedding geometry, cluster
structure, composite score — and pin *nothing* about prediction, for the reason in
"What a pass does not mean" below. `swiss_roll` is the one that pins the path from
embedding coordinates to a predicted value.

## What is pinned, and why in that form

| what | compared by | why not the obvious thing |
|---|---|---|
| prediction scores per target | `rtol=1e-3` | — the number that matters |
| `composite_score`, UMAP/HDBSCAN metrics | `rtol=1e-6` | — |
| cluster count | exact | an integer has no float drift |
| cluster structure | adjusted Rand index ≥ 0.95 | cluster **ids are arbitrary**; label equality would fail on a relabelling that changed nothing |
| embedding geometry | pairwise-distance correlation ≥ 0.999 | UMAP is defined only **up to rotation and reflection**, so coordinates are not comparable across runs |

Every float tolerance is **chosen**, not measured: local run-to-run variation is
exactly zero, so the numbers are cross-machine allowances for CI. Each is
labelled in `test_numerical_regression.py`; do not let a chosen number start
reading as a measured one. Sources in
`dev-docs/issues/reproducibility_tolerances_2026_08.md`.

## The config, and why it is not the shared fixture

`regression_config.py`. It is the `midbudget-serial` arm of
`scripts/measure_reproducibility.py`, the only measured config that is both
reproducible (20 of 20 metrics identical over three repeats at seed 42) and
non-degenerate (3 clusters, `noise_fraction` 0.1).

`emuses_pipeline_results` (`tests/conftest.py`) cannot be used: it runs
`optim_dict_hcp`, in which every parameter is fixed, so the search collapses to
one trial and HDBSCAN returns **zero clusters with all 40 points labelled
noise**. An adjusted Rand index between two all-noise labellings is 1.0 by
construction — the assertion could never fail. `test_baseline_is_not_degenerate`
exists so this suite fails loudly if its own config ever drifts into that state.

Serial search (`umap_jobs=1`) is load-bearing: `optuna.study.optimize(n_jobs>1)`
schedules trials concurrently and no seed fixes the result.

## Regenerating the baselines

```bash
pytest tests/regression --regen-baselines
```

**This is a deliberate act.** The commit message must say what moved the numbers
and why. A missing baseline fails the suite rather than being written silently —
otherwise the suite ratchets to whatever the code currently does, which is the
one failure mode a regression suite exists to prevent.

The baseline records the config that produced it, and
`test_baseline_describes_this_config` fails if the two drift apart, so numbers
from one config can never be compared against another.

## What a pass does not mean

`test_data/features.csv` is 48 samples × 7 features (40 after the split). Enough to
catch a regression; **not** enough to judge scientific quality.

These tolerances detect code changes **at a fixed seed**. At a different master
seed the same config gives a cluster ARI of 0.0 against this baseline and
`Mean_Score` moves from −0.48 to −1.00. That is an under-converged search on 40
samples, not a defect, and this suite does not measure it.

### The prediction baselines on the 40-sample datasets are degenerate (2026-09-06)

On **both** of them, in **every** fold, the winning ElasticNet has all coefficients
exactly zero. The L1 penalty zeroes them — there is nothing to fit on 40 samples of
that fixture — so the model is a constant intercept, the training-fold mean, and
`target_0_*_Score` is a function of the fold split alone. It is **mathematically
independent of the embedding coordinates the models were handed.**

Consequence: those eight numbers per dataset survive *any* change to the coordinate
system, correct or not. Found by switching the whole pipeline from per-axis to
isotropic rescaling and watching all 16 tests pass **bit-identically** while the
narrow embedding axis went from spanning 1.0 to spanning 0.24. The finding is now
recorded as data, not prose: `n_constant_prediction_models` in each baseline file
reads `5/5` and `10/10` against `0/5` for `swiss_roll`.

This is why `swiss_roll` was added rather than the tolerances tightened. Its target
is the roll's own generative parameter, so the signal is real (`Mean_Score` 0.9962)
and 4 of its 5 folds are won by a kernel over the embedding — the model family that
reads coordinates directly. Demonstrated, not assumed: reverting the rescale to
per-axis fails `test_prediction_scores[swiss_roll]` while
`test_prediction_scores[regression]` and `[multi_target_regression]` both pass.

`test_some_dataset_pins_the_coordinate_to_prediction_path` fails if the suite ever
returns to the state where no dataset can see such a change. It reads baselines
only, so it costs 0.07 s and needs no pipeline run.

**The signature was visible in 2026-08-23 and misread.** See the last line of
"Proven to fail" below: a real one-line change to the science moved the geometry and
left prediction scores untouched. That was recorded as an argument for pinning more
than "the number that matters". It was also, unread, the first evidence that the
prediction numbers could not move at all.

## Proven to fail (2026-08-23)

Perturbed rather than assumed. Every assertion family was made to fail:

* each baseline field nudged past its tolerance → all six families failed, with
  the two degeneracy guards still passing;
* baseline replaced by an all-noise labelling → `test_baseline_is_not_degenerate`
  failed;
* one line of production code changed (`UMAP_utils`, model seed shifted by one,
  no config touched) → composite/search metrics, cluster structure and embedding
  geometry all failed.

Worth knowing from that last one: **prediction scores and cluster count did not
move.** Pinning only "the number that matters" would have missed a real change
to the science.

Read again on 2026-09-06, that sentence says more than it was taken to say at the
time: on these two datasets the prediction scores did not move because **they
cannot** — see "The prediction baselines … are degenerate" above.

## Proven to fail (2026-09-06, the `swiss_roll` additions)

* rescaling reverted from isotropic to per-axis → `test_prediction_scores[swiss_roll]`
  failed and the other two datasets' prediction tests **passed**, which is the whole
  reason the dataset exists;
* `prediction_depends_on_coordinates` flipped to `false` in the `swiss_roll` baseline
  → `test_some_dataset_pins_the_coordinate_to_prediction_path` failed, naming the
  per-dataset breakdown;
* the liveness measurement itself was not perturbed synthetically — it is exercised
  by three real datasets that disagree, reporting `5/5` and `10/10` constant models
  against `0/5`.
