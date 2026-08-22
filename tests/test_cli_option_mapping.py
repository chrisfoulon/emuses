"""Every ``emuses full`` option must reach the pipeline, or be declared as not reaching it.

Options travel CLI -> ``_convert_typer_args_to_service_config`` -> ``_context_to_emuses_args``
-> ``PipelineConfig`` -> stages. The middle step assigns args one at a time by hand, so an
option that nobody remembers to add there is not an error: it is silently dropped, and the
run falls back to the ``PipelineConfig`` dataclass default. The user passes a flag, the tool
prints no warning, and the flag does nothing.

That is exactly what had happened to ``--hdbscan_core_dist_n_jobs``,
``--hdbscan_approx_min_span_tree``, ``--input_file_list`` and ``--recursive-input-file-search``
before 2026-08-22. It is a bad failure mode for a scientific tool, because the run looks
successful and the result is not the one that was asked for.

The two lists are maintained independently, so this test pins the relationship between them
rather than trusting either. Declaring the exceptions as data is deliberate: deriving them
from the code would make the check circular and unable to fail.
"""

import ast
import inspect
import textwrap
from pathlib import Path

import pytest

from emuses.cli.main import full
from emuses.foundation_fastapi_service.pipeline_runner import PipelineRunner

# Options that legitimately stop at the CLI. They configure how the job is transported and
# displayed, not what the pipeline computes, so they must NOT be forwarded to PipelineConfig.
TRANSPORT_ONLY = {
    "use_service",
    "service_url",
    "token",
    "interactive",
    "service_timeout",
    "umap_timeout",
    "heatmap_timeout",
    "prediction_timeout",
}

# Options the CLI advertises that nothing in the codebase reads. Mapping them would
# accomplish nothing - they need an implementation or removal from the CLI, which is a
# product decision rather than a plumbing one. Listed here so they stay visible instead of
# blending in with the correctly-mapped ones.
#
# `min_cluster_size` is the clearest case: HDBSCAN's min_cluster_size is chosen by Optuna
# over the range [5, 50] (UMAP_utils.py:73), so a user-supplied fixed value has nothing to
# act on and is overwritten by the search.
NOT_IMPLEMENTED = {
    "min_cluster_size",
    "model_selection",
    "use_enhanced_pipeline",
    "parallel_models",
    "inspect_data_state",
}

# CLI parameter name -> the args attribute it is mapped onto, where the two differ.
# The flag is spelled --recursive-input-file-search but Typer binds it to the Python
# parameter `recursive_search`, while the only consumer (emuses_pipeline.py:327) reads
# `recursive_input_file_search`.
RENAMED = {"recursive_search": "recursive_input_file_search"}

# Same convention as tests/conftest.py and tests/test_architecture_boundary.py: never depend
# on the cwd, which the isolation fixtures move into tmp_path.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _cli_option_names() -> set:
    """Names of every parameter the ``full`` command accepts."""
    return set(inspect.signature(full).parameters)


def _mapped_arg_names() -> set:
    """Attributes assigned on ``args`` inside ``_context_to_emuses_args``.

    Parsed rather than executed: calling it needs a full context, and the point is to
    inspect what the source assigns, not what one particular input produces.
    """
    source = inspect.getsource(PipelineRunner._context_to_emuses_args)
    tree = ast.parse(textwrap.dedent(source))

    assigned = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for target in node.targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == "args"
            ):
                assigned.add(target.attr)
    return assigned


def _unmapped_options() -> set:
    """CLI options that reach neither the pipeline nor a declared exception list."""
    mapped = _mapped_arg_names()
    return {
        name
        for name in _cli_option_names()
        if RENAMED.get(name, name) not in mapped
        and name not in TRANSPORT_ONLY
        and name not in NOT_IMPLEMENTED
    }


def test_every_cli_option_reaches_the_pipeline():
    """No `emuses full` option may be silently dropped on the way to PipelineConfig."""
    unmapped = _unmapped_options()

    assert not unmapped, (
        f"{len(unmapped)} CLI option(s) never reach the pipeline: {sorted(unmapped)}.\n\n"
        "Each of these is accepted on the command line and then discarded, so the run "
        "silently uses the PipelineConfig default instead of the requested value.\n\n"
        "Fix by either:\n"
        "  - assigning it in PipelineRunner._context_to_emuses_args, or\n"
        "  - adding it to TRANSPORT_ONLY if it must not reach the pipeline, or\n"
        "  - adding it to NOT_IMPLEMENTED if nothing reads it yet.\n"
        "Do not add it to an exception list just to make this test pass."
    )


@pytest.mark.parametrize(
    "option, consumer",
    [
        ("hdbscan_core_dist_n_jobs", "emuses/pipelines/umap_stage.py"),
        ("hdbscan_approx_min_span_tree", "emuses/pipelines/umap_stage.py"),
        ("input_file_list", "emuses/pipelines/emuses_pipeline.py"),
        ("recursive_search", "emuses/pipelines/emuses_pipeline.py"),
    ],
)
def test_previously_dropped_options_are_mapped(option, consumer):
    """The four options this test was written for, pinned individually.

    A general check can be satisfied by widening an exception list. These four have real
    consumers, so name them explicitly - reintroducing the bug for any one of them should
    fail loudly rather than shifting a count.
    """
    assert option in _cli_option_names(), f"{option} is no longer a CLI option"
    assert RENAMED.get(option, option) in _mapped_arg_names(), (
        f"--{option.replace('_', '-')} is accepted by the CLI but no longer mapped in "
        f"_context_to_emuses_args, so it will not reach {consumer} and the flag will do "
        "nothing."
    )

    # The mapping is only worth anything if something downstream still reads the attribute.
    # Checking the consumer actually references it catches the case where the option is
    # dutifully mapped into a config nobody consults any more.
    consumer_path = PROJECT_ROOT / consumer
    assert consumer_path.exists(), f"declared consumer {consumer} no longer exists"

    attribute = RENAMED.get(option, option)
    assert attribute in consumer_path.read_text(), (
        f"{consumer} no longer references {attribute}, so mapping it achieves nothing. "
        "Either the consumer moved - update this test - or the option became dead and "
        "belongs in NOT_IMPLEMENTED."
    )


def test_not_implemented_options_are_still_unread():
    """Keep NOT_IMPLEMENTED honest in both directions.

    If one of these gains a consumer and a mapping, it should be removed from the list
    rather than left behind, where it would suppress a future regression for that option.
    """
    mapped = _mapped_arg_names()
    now_mapped = {name for name in NOT_IMPLEMENTED if name in mapped}

    assert not now_mapped, (
        f"{sorted(now_mapped)} are mapped to the pipeline but still listed as "
        "NOT_IMPLEMENTED. Remove them from that list so they are covered by the main check."
    )


def test_the_checker_has_teeth():
    """The check must fail when an option is genuinely dropped.

    Without this, a bug in the extraction - a changed AST shape, a renamed function - would
    make every list come back empty and the suite would report success while checking
    nothing.
    """
    real_mapped = _mapped_arg_names()
    assert real_mapped, "extracted no assignments at all; the AST walk is broken"
    assert "output_folder" in real_mapped, "expected output_folder among mapped args"

    # Simulate dropping a mapped, non-exempt option and confirm the rule catches it.
    victim = "umap_trials"
    assert victim in _cli_option_names()
    assert victim in real_mapped

    damaged = real_mapped - {victim}
    would_be_unmapped = {
        name
        for name in _cli_option_names()
        if RENAMED.get(name, name) not in damaged
        and name not in TRANSPORT_ONLY
        and name not in NOT_IMPLEMENTED
    }

    assert victim in would_be_unmapped, (
        "the rule does not notice a dropped option, so it cannot detect the regression "
        "it exists to prevent"
    )
