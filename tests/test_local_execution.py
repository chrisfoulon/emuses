"""Local mode runs in this process, and the shorter path is not the unvalidated path.

ADR §4 defines local mode as "CLI, file-based storage, in-process execution". Until
2026-08-23 the CLI forked a FastAPI service, waited for it to become healthy, and posted
its own job over HTTP to localhost. Beyond the wasted process and port, that silently
changed behaviour: the pipeline ran in a ``multiprocessing.Process`` child, where
``is_subprocess_context()`` is True and ``get_safe_n_jobs()`` clamps ``n_jobs`` to 1. So
``--n_jobs`` did nothing on the CLI while working normally through the Python API.

Two risks come with removing the fork, and each has a test here:

- **Validation could be skipped.** The required-field checks, special-dataset handling and
  the output-path checks added after the shell-injection cleanup all lived inside the HTTP
  endpoint. They are now in ``prepare_pipeline_context``, which both paths call.
- **The numbers could move**, because ``n_jobs`` is no longer clamped. They do not: at the
  regression config a CLI run reproduced both the forked CLI run and the API-produced
  baseline on all 18 scalar metrics, with cluster ARI 1.0 and embedding distance
  correlation 1.0. That is measurement, not inference, and it is why this change was safe
  to make.
"""

import ast
import inspect
import textwrap
from unittest.mock import AsyncMock, patch

import pytest


def test_local_execution_never_needs_a_job_manager():
    """``run_pipeline_locally`` passes ``job_manager=None`` rather than a stub.

    A stub would quietly absorb a future call that ought to fail loudly. This pins the
    property the None depends on, so the claim cannot go stale in a comment.
    """
    from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

    source = textwrap.dedent(
        inspect.getsource(PipelineRunner._run_pipeline_in_process)
    )
    tree = ast.parse(source)

    used = {
        node.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "self"
    }

    assert "job_manager" not in used, (
        "_run_pipeline_in_process now uses self.job_manager, but run_pipeline_locally "
        "constructs PipelineRunner(job_manager=None) for the CLI's local path. Either "
        "give the local path a real JobManager or keep the method free of it - do not "
        "paper over it with a stub."
    )


def test_the_local_path_cannot_skip_endpoint_validation():
    """Both entry points must build their context through the same function.

    Security checks must not be reachable only over HTTP.
    """
    from emuses.cli.main import _execute_locally_in_process
    from emuses.foundation_fastapi_service import app as app_module

    def _calls(func):
        """Names actually *called* in func - not merely mentioned.

        A substring check would pass on the import line and the docstring alone, which
        it did until a perturbation caught it: deleting the real call left the test
        green.
        """
        tree = ast.parse(textwrap.dedent(inspect.getsource(func)))
        return {
            node.func.id if isinstance(node.func, ast.Name) else node.func.attr
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, (ast.Name, ast.Attribute))
        }

    assert "prepare_pipeline_context" in _calls(_execute_locally_in_process), (
        "the CLI local path no longer calls prepare_pipeline_context, so it can run a "
        "config the HTTP endpoint would have rejected."
    )
    assert "prepare_pipeline_context" in _calls(app_module.submit_full_pipeline_job), (
        "the endpoint no longer calls prepare_pipeline_context, so the two paths have "
        "drifted apart - which is the failure this shared function exists to prevent."
    )

    # And the function must actually validate, not merely exist.
    with pytest.raises(ValueError, match="input_dataset"):
        app_module.prepare_pipeline_context({"output_folder": "/tmp/x"})
    with pytest.raises(ValueError, match="output_folder"):
        app_module.prepare_pipeline_context({"input_dataset": "/tmp/x"})


class _Renderer:
    def render_status(self, *args, **kwargs):
        return ""


@pytest.mark.parametrize(
    "extra_kwargs, expected, unexpected",
    [
        ({}, "_execute_locally_in_process", "_execute_via_unified_service"),
        (
            {"use_service": True},
            "_execute_via_unified_service",
            "_execute_locally_in_process",
        ),
        (
            {"service_url": "http://elsewhere:9000"},
            "_execute_via_remote_service",
            "_execute_locally_in_process",
        ),
    ],
    ids=["default-is-in-process", "--service-forks", "--service-url-goes-remote"],
)
def test_local_mode_dispatch(tmp_path, extra_kwargs, expected, unexpected):
    """Default local runs in-process; --service and --service-url each opt out.

    Both flags used to be popped from kwargs and discarded, so neither did anything.
    """
    from emuses.cli import main as cli_main

    kwargs = {
        "output_folder": tmp_path / "out",
        "input_dataset": tmp_path / "in.csv",
        "scores": tmp_path / "scores.csv",
        **extra_kwargs,
    }

    with patch.object(cli_main, "_execute_locally_in_process", new=AsyncMock()) as local, \
         patch.object(cli_main, "_execute_via_unified_service", new=AsyncMock()) as unified, \
         patch.object(cli_main, "_execute_via_remote_service", new=AsyncMock()) as remote, \
         patch.object(cli_main, "StatusRenderer", _Renderer):
        import asyncio

        asyncio.run(cli_main._full_async(**kwargs))

    called = {
        "_execute_locally_in_process": local,
        "_execute_via_unified_service": unified,
        "_execute_via_remote_service": remote,
    }
    assert called[expected].await_count == 1, f"{expected} should have been used"
    assert called[unexpected].await_count == 0, f"{unexpected} should not have been used"
