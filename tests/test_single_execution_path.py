"""Every deployment mode executes through the EMUSES service. There is one path.

ADR §4. Local, lab and server modes all submit to a FastAPI service - local mode
auto-starts one rather than being special-cased into a direct call. The reason is
maintenance, not purity: a second local path means every change to logging, progress
reporting, job status or error handling has to be made twice, in two shapes, and the
second one drifts.

That is not hypothetical. It was tried on 2026-08-23 and reverted the same day. Moving
``full`` in-process took perhaps forty lines and immediately produced:

- a **third** progress mechanism (service writes to the job record, CLI polls and prints,
  local path printed directly) with no interrupt handling and no job record;
- a leaked temporary scores file, because ``_cleanup_temp_scores_file`` lives in
  ``execute_pipeline``'s ``finally`` and the direct call bypassed it;
- no timeout, because that is also applied by ``execute_pipeline``;
- a CLI where ``full`` behaved one way and ``umap``/``heatmap`` another.

The other half of the argument is that going over HTTP locally *catches things*. Phase 1C
is the evidence: ``/api/v1/jobs/pipeline/umap`` did not exist on the server. The CLI built
that URL, got a 404, and the bug was found on a laptop. In-process, a missing route stays
invisible until someone deploys.

Known cost, accepted deliberately: the pipeline runs in a ``multiprocessing.Process``
child, so ``get_safe_n_jobs()`` clamps ``n_jobs`` to 1 and ``--n_jobs`` does nothing on the
CLI. That is a real defect, tracked separately - the fix is to make the clamp precise
(its documented hazard is loky-specific, and the pipeline runs on the threading backend),
not to bypass the service.
"""

import ast
import asyncio
import inspect
import textwrap
from unittest.mock import AsyncMock, patch

import pytest

# Functions that execute a pipeline. If the CLI ever calls one of these directly it has
# grown a second execution path, which is the thing this file exists to prevent.
PIPELINE_ENTRY_POINTS = {
    "_run_pipeline_in_process",
    "_execute_pipeline_stages",
    "EMUSESPipeline",
    "run_pipeline_locally",
}

# Declared exceptions to the rule, as data so they stay visible instead of blending in -
# the same treatment as NOT_IMPLEMENTED in tests/test_cli_option_mapping.py.
#
# Empty since 2026-08-24 (Phase 1F). The one entry was `_execute_inference_locally`:
# `emuses inference` built an EMUSESPipeline and ran InferenceStage directly in the CLI
# process, never touching the service, which is what stopped a lab from having one person
# train a model and others run inference against it on a server. It now submits an
# inference job like every other command.
#
# An empty set is not an invitation to add to it. A new entry needs a decision.
KNOWN_LOCAL_EXECUTION = set()


def _called_names(func):
    """Names actually *called* in ``func`` - not merely mentioned.

    A substring check is not enough, and that is not a guess: an earlier version of this
    test used one, and a perturbation showed it passed on the import line and the
    docstring alone while the real call had been deleted.
    """
    tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
    return {
        node.func.id if isinstance(node.func, ast.Name) else node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, (ast.Name, ast.Attribute))
    }


def test_the_cli_never_executes_a_pipeline_itself():
    """The CLI submits jobs; it does not run pipelines.

    Fails if someone reintroduces a direct local path, whatever it is called.
    """
    from emuses.cli import main as cli_main

    source = (
        __import__("pathlib").Path(inspect.getfile(cli_main))
    ).read_text()
    tree = ast.parse(source)

    # Map every call to the enclosing top-level function, so a known exception can be
    # excused by name rather than by line number, which would rot on the next edit.
    offenders = {}
    for func in ast.walk(tree):
        if not isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if func.name in KNOWN_LOCAL_EXECUTION:
            continue
        for node in ast.walk(func):
            if not isinstance(node, ast.Call):
                continue
            name = (
                node.func.id
                if isinstance(node.func, ast.Name)
                else getattr(node.func, "attr", None)
            )
            if name in PIPELINE_ENTRY_POINTS:
                offenders.setdefault(func.name, set()).add(name)

    assert not offenders, (
        f"emuses/cli/main.py executes pipelines directly in {offenders}. Every mode must "
        "go through the service (ADR §4) so there is one path to maintain. See this "
        "module's docstring for what a second path cost when it was tried. If this is "
        "genuinely intended, add it to KNOWN_LOCAL_EXECUTION with a reason - do not "
        "delete the check."
    )


def test_the_known_exception_still_exists():
    """Keep KNOWN_LOCAL_EXECUTION honest in the other direction.

    If inference is moved onto the service, this list must shrink - otherwise it silently
    licenses a future regression for a function that no longer needs the exemption.
    """
    from emuses.cli import main as cli_main

    source = (__import__("pathlib").Path(inspect.getfile(cli_main))).read_text()
    tree = ast.parse(source)

    defined = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    still_local = set()
    for func in ast.walk(tree):
        if (
            isinstance(func, (ast.FunctionDef, ast.AsyncFunctionDef))
            and func.name in KNOWN_LOCAL_EXECUTION
        ):
            for node in ast.walk(func):
                if isinstance(node, ast.Call):
                    name = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else getattr(node.func, "attr", None)
                    )
                    if name in PIPELINE_ENTRY_POINTS:
                        still_local.add(func.name)

    stale = (KNOWN_LOCAL_EXECUTION & defined) - still_local
    assert not stale, (
        f"{sorted(stale)} no longer execute a pipeline directly, so they should be "
        "removed from KNOWN_LOCAL_EXECUTION and covered by the main check again."
    )
    missing = KNOWN_LOCAL_EXECUTION - defined
    assert not missing, (
        f"{sorted(missing)} are listed as exceptions but no longer exist in the CLI. "
        "Remove them from KNOWN_LOCAL_EXECUTION."
    )


def test_validation_is_not_locked_inside_the_http_handler():
    """``prepare_pipeline_context`` stays a named, testable function.

    Kept from the reverted work because it is right regardless: required-field checks,
    special-dataset handling and the post-shell-injection output-path checks should be
    callable and testable, not buried in a route body.
    """
    from emuses.foundation_fastapi_service import app as app_module

    assert "prepare_pipeline_context" in _called_names(
        app_module.submit_full_pipeline_job
    ), "the full pipeline endpoint no longer routes through prepare_pipeline_context"

    with pytest.raises(ValueError, match="input_dataset"):
        app_module.prepare_pipeline_context({"output_folder": "/tmp/x"})
    with pytest.raises(ValueError, match="output_folder"):
        app_module.prepare_pipeline_context({"input_dataset": "/tmp/x"})


class _Renderer:
    def __init__(self):
        self.messages = []

    def render_status(self, level, message="", *args, **kwargs):
        self.messages.append((level, message))
        return ""


@pytest.mark.parametrize(
    "extra_kwargs, expected, unexpected",
    [
        ({}, "_execute_via_unified_service", "_execute_via_remote_service"),
        (
            {"service_url": "http://elsewhere:9000"},
            "_execute_via_remote_service",
            "_execute_via_unified_service",
        ),
    ],
    ids=["local-auto-starts-a-service", "--service-url-goes-remote"],
)
def test_local_mode_dispatch(tmp_path, extra_kwargs, expected, unexpected):
    """Local auto-starts a service; --service-url opts into a remote one.

    ``--service-url`` used to be popped from kwargs and discarded, so it did nothing.
    """
    from emuses.cli import main as cli_main

    kwargs = {
        "output_folder": tmp_path / "out",
        "input_dataset": tmp_path / "in.csv",
        "scores": tmp_path / "scores.csv",
        **extra_kwargs,
    }

    with patch.object(cli_main, "_execute_via_unified_service", new=AsyncMock()) as unified, \
         patch.object(cli_main, "_execute_via_remote_service", new=AsyncMock()) as remote, \
         patch.object(cli_main, "StatusRenderer", _Renderer):
        asyncio.run(cli_main._full_async(**kwargs))

    calls = {
        "_execute_via_unified_service": unified,
        "_execute_via_remote_service": remote,
    }
    assert calls[expected].await_count == 1, f"{expected} should have been used"
    assert calls[unexpected].await_count == 0, f"{unexpected} should not have been used"


def test_inference_submits_a_job_to_a_route_that_exists(tmp_path):
    """``emuses inference`` submits like every other command, and the URL resolves.

    Two halves, because Phase 1C showed that getting the first one right is not enough:
    the CLI built ``/api/v1/jobs/pipeline/umap``, the service had no such route, and every
    ``emuses umap`` run fell through to a local path that then mistook it for ``full``. So
    the pipeline type the CLI sends is taken from the call itself and checked against the
    service's registered routes, rather than both being written out by hand.
    """
    from emuses.cli import main as cli_main

    with patch.object(cli_main, "_execute_via_remote_service", new=AsyncMock()) as remote, \
         patch.object(cli_main, "_execute_via_unified_service", new=AsyncMock()) as unified, \
         patch.object(cli_main, "StatusRenderer", _Renderer):
        asyncio.run(
            cli_main._inference_async(
                data=tmp_path / "in.csv",
                output=tmp_path / "out",
                model=tmp_path / "model",
                columns_are_features=True,
                input_header=0,
            )
        )

    assert remote.await_count == 1, "inference did not submit to the service"
    assert unified.await_count == 0, "the remote submission succeeded, so no fallback"

    pipeline_type, config = remote.await_args[0][0], remote.await_args[0][1]
    assert pipeline_type == "inference"

    # The two positional CLI arguments have to arrive under the keys the service reads.
    assert config["input_dataset"] == str(tmp_path / "in.csv")
    assert config["output_folder"] == str(tmp_path / "out")
    assert config["model"] == str(tmp_path / "model")
    assert config["columns_are_features"] is True
    assert config["input_header"] == 0

    from emuses.foundation_fastapi_service.app import app as service_app

    routes = {getattr(route, "path", None) for route in service_app.routes}
    assert f"/api/v1/jobs/pipeline/{pipeline_type}" in routes, (
        f"the CLI submits {pipeline_type} jobs to a route the service does not define. "
        "That is the Phase 1C defect: a 404 the user sees as a silent fallback."
    )


def test_inference_jobs_run_no_training_stages():
    """An inference job loads a model; it must not fit one.

    The endpoint disables the training stages explicitly. Without that, the runner's
    defaults (``umap_stage_enabled`` and ``heatmap_stage_enabled`` both default to True)
    would have an inference request retrain the model it was asked to apply.
    """
    from emuses.foundation_fastapi_service import app as app_module

    source = inspect.getsource(app_module.submit_inference_pipeline_job)
    for flag in ("umap_stage_enabled", "heatmap_stage_enabled", "prediction_stage_enabled"):
        assert f'config["{flag}"] = False' in source, (
            f"{flag} is not disabled for inference jobs, so the runner's default (True) "
            "would add a training stage to an inference run."
        )


def test_service_flag_says_it_does_nothing_rather_than_silently_doing_nothing():
    """``--service`` is redundant now that every mode uses a service.

    Leaving it accepted and inert is the Phase 1A defect: a flag the user passes, that
    changes nothing, with no warning. It warns instead.
    """
    from emuses.cli import main as cli_main

    renderer = _Renderer()

    with patch.object(cli_main, "_execute_via_unified_service", new=AsyncMock()), \
         patch.object(cli_main, "_execute_via_remote_service", new=AsyncMock()), \
         patch.object(cli_main, "StatusRenderer", lambda: renderer):
        asyncio.run(
            cli_main._full_async(
                output_folder="/tmp/out",
                input_dataset="/tmp/in.csv",
                use_service=True,
            )
        )

    warnings = [m for level, m in renderer.messages if "--service" in m]
    assert warnings, (
        "passing --service produced no message. It has no effect, so it must say so."
    )
    assert any("--service-url" in m for m in warnings), (
        "the warning should point at --service-url, which is the flag that does work."
    )
