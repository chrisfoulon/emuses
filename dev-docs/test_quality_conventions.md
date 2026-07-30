# EMUSES Test Quality Conventions

EMUSES-specific testing conventions that a generic test-quality methodology cannot infer.
The general improvement process (baselining, failure classification, prioritised fix cycles)
lives in the LAD `test-quality` skill — this file covers only what is particular to this repo.

Distilled 2026-07-30 from `.lad/TEST_QUALITY_FRAMEWORK.md` and
`.lad/FRAMEWORK_IMPLEMENTATION_GUIDE.md` during the LAD v2 migration. Both originals are archived
in `dev-docs/project-history/phase-implementations/`.

## Regression gate

`python scripts/dev_test_runner.py` is the pre-push gate — **13/13 tests, expected to pass**. Run it
after any batch of test changes, not only at the end. It is fast (a few seconds) and is what CI
previews on feature branches.

Full validation is `pytest -q --tb=short`, but see the environment caveat below before reading
anything into its output.

## Real data over synthetic data

`test_data/` holds small real datasets. Prefer them over `np.random.rand()` — synthetic data
produces edge cases the pipeline never sees in practice, which shows up as false failures.

| File | Shape | Use |
|---|---|---|
| `test_data/features.csv` | 50 × 8 | Input features |
| `test_data/regression_scores_multitarget.csv` | 50 × 2 | Multi-target regression |
| `test_data/regression_scores.csv` | 50 × 1 | Single-target regression |
| `test_data/classification_labels.csv` | 50 × 1 | Binary classification |
| `test_data/classification_labels_multiclass.csv` | 50 × 1 | Multi-class classification |

The established 30/20 train/test split:

```python
@classmethod
def setup_class(cls):
    """Load real test data for validation."""
    project_root = Path(__file__).parent.parent.parent
    cls.features = pd.read_csv(project_root / 'test_data/features.csv', header=None).values
    cls.targets = pd.read_csv(project_root / 'test_data/regression_scores_multitarget.csv', header=None).values
    cls.train_coords = cls.features[:30, :2]   # first 2 features as coordinates
    cls.test_coords = cls.features[30:, :2]    # last 20 samples for testing
    cls.train_targets = cls.targets[:30]
    cls.test_targets = cls.targets[30:]
```

When converting a test from synthetic to real data, change **only the data source**. Leave the test
logic and assertions alone — if assertions need changing too, that is a separate change and should be
reasoned about separately.

For integration tests, `tests/conftest.py` exposes a session-scoped `emuses_pipeline_results` fixture
that runs the full pipeline once per session across all four data modes. Use it rather than invoking
the pipeline per-test.

## Environment caveat

A full `pytest` run currently reports ~121 **collection** errors on a clean checkout. These are
missing optional dependencies in the active interpreter (e.g. `ModuleNotFoundError: hdbscan`), not
repo breakage. Confirm your environment has the analysis dependencies installed before treating
collection errors as real failures — otherwise you will chase phantom regressions.

## Coverage targets

90% for newly added code. This is a target for code you write, not a gate to retrofit across the
existing repo. Historical priority ordering when hunting gaps: core pipelines and integration points
first, validation and performance second, edge cases and utilities last.
