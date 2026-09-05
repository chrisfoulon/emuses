"""Where a set of pinned numbers came from.

A baseline that records only ``{config, metrics}`` cannot answer the one
question every failure of this suite raises: *did the code change, or did the
machine?* On 2026-09-05 that ambiguity cost a full day. CI reported the cluster
count moving 3 -> 4 and the composite score moving 0.038, and distinguishing
"a real regression" from "a different CPU" needed five library upgrades, a
thread-count experiment and a seed-variation experiment to settle.

Every one of those experiments read a value this module now records. The point
is to make the next occurrence a one-line diff instead of a day.

What is recorded, and why each entry earned its place:

* ``llvm_cpu_name`` -- the codegen target llvmlite hands numba, e.g.
  ``meteorlake`` locally versus whatever the runner is. **This is the prime
  suspect** for cross-machine drift: numba compiles UMAP's inner loops for the
  host CPU, so a different target changes the floating-point result, which
  crosses an HDBSCAN decision boundary, which is then amplified downstream.
* ``llvm_cpu_features`` -- a digest, not the flag string, which is ~1 kB of
  noise. Catches the case where the CPU *name* matches but the enabled feature
  set does not.
* ``packages`` -- the numerical stack. Ruled out as the cause on 2026-09-05
  (the local environment was brought up to the pinned versions and still
  reproduced the baseline exactly, while CI did not), but ruled out is a
  finding that has to be re-established every time, and it costs one dict.
* ``python``/``platform`` -- cheap, and the first thing anyone asks.

Nothing here is asserted on. Environment drift is *reported*, never a failure:
this suite exists to catch code changes, and failing because someone ran it on
a different laptop would train people to ignore it.
"""

import hashlib
import platform

try:  # pragma: no cover - trivial
    from importlib.metadata import PackageNotFoundError, version as _version
except ImportError:  # pragma: no cover - Python < 3.8, not supported anyway
    _version = None
    PackageNotFoundError = Exception


# The numerical stack, in the order a human wants to read it. `numba` and
# `llvmlite` are last because they are the interesting ones and the eye lands
# at the end of a list.
PINNED_PACKAGES = (
    "numpy",
    "scipy",
    "scikit-learn",
    "pandas",
    "joblib",
    "optuna",
    "umap-learn",
    "hdbscan",
    "numba",
    "llvmlite",
)


def _package_versions():
    versions = {}
    for name in PINNED_PACKAGES:
        try:
            versions[name] = _version(name)
        except PackageNotFoundError:
            versions[name] = "<not installed>"
        except Exception:  # pragma: no cover - metadata is not worth a crash
            versions[name] = "<unreadable>"
    return versions


def _llvm_target():
    """What llvmlite will compile numba's kernels for.

    Wrapped because provenance must never be the thing that breaks the suite:
    a missing or changed llvmlite API costs an "<unavailable>", not a run.
    """
    try:
        import llvmlite.binding as llvm

        name = llvm.get_host_cpu_name()
        flags = llvm.get_host_cpu_features().flatten()
        digest = hashlib.sha256(flags.encode()).hexdigest()[:12]
        return name, digest
    except Exception:  # pragma: no cover
        return "<unavailable>", "<unavailable>"


def collect_provenance():
    """Everything observed to move these numbers, as plain JSON-able data."""
    cpu_name, cpu_features = _llvm_target()
    return {
        "python": platform.python_version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "llvm_cpu_name": cpu_name,
        "llvm_cpu_features": cpu_features,
        "packages": _package_versions(),
    }


def describe_environment_drift(recorded):
    """Human-readable diff of a baseline's environment against this one.

    Returns ``""`` when nothing differs, so it can be appended unconditionally
    to an assertion message without adding noise to the common case.
    """
    if not recorded:
        return (
            "\n\n[environment] This baseline predates provenance recording, so "
            "there is nothing to compare against. Regenerate it "
            "(`pytest tests/regression --regen-baselines`) on a machine you "
            "trust, in a commit that says so, and the next failure will be able "
            "to tell a code change from a machine change."
        )

    current = collect_provenance()
    lines = []

    for key in ("python", "platform", "machine", "llvm_cpu_name", "llvm_cpu_features"):
        was, now = recorded.get(key, "<absent>"), current[key]
        if was != now:
            lines.append(f"  {key}: baseline {was!r} -> here {now!r}")

    recorded_packages = recorded.get("packages", {})
    for name in PINNED_PACKAGES:
        was = recorded_packages.get(name, "<absent>")
        now = current["packages"][name]
        if was != now:
            lines.append(f"  {name}: baseline {was} -> here {now}")

    if not lines:
        return (
            "\n\n[environment] Identical to the baseline's, down to the LLVM "
            "codegen target. This is a code change, not machine drift."
        )

    return (
        "\n\n[environment] This run differs from the one that produced the "
        "baseline:\n" + "\n".join(lines) + "\n"
        "  A differing llvm_cpu_name alone is enough to move these numbers; see "
        "this module's docstring. Environment drift is reported, never asserted."
    )
