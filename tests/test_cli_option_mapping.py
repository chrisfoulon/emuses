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


def _find_all(haystack: str, needle: str):
    """Every index of ``needle`` - the same declaration can appear more than once."""
    start = haystack.find(needle)
    while start != -1:
        yield start
        start = haystack.find(needle, start + 1)


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


# ---------------------------------------------------------------------------------------
# Phase 1C: the three pipeline commands share ONE option declaration.
#
# `umap` and `heatmap` used to declare only output_folder and input_dataset, so every
# option above was accepted by `full` and rejected by the other two. Copying `full`'s
# block twice would have fixed the symptom and recreated the bug this file exists for -
# three hand-maintained lists that drift silently. They are stamped from one signature
# instead, and these tests pin that relationship rather than trusting it.
# ---------------------------------------------------------------------------------------

from emuses.cli.main import heatmap, umap  # noqa: E402
from emuses.cli.pipeline_options import (  # noqa: E402
    SHARED_PIPELINE_SIGNATURE,
    shared_option_names,
)

PIPELINE_COMMANDS = {"full": full, "umap": umap, "heatmap": heatmap}


@pytest.mark.parametrize("name", sorted(PIPELINE_COMMANDS))
def test_pipeline_commands_share_one_option_declaration(name):
    """All three commands must expose exactly the shared option set.

    Not "roughly the same" - identical. A command that gains an option the others lack is
    the Phase 1A failure mode returning: the flag works on one command and is silently
    unavailable on another.
    """
    command = PIPELINE_COMMANDS[name]
    actual = set(inspect.signature(command).parameters)

    assert actual == shared_option_names(), (
        f"`emuses {name}` does not expose the shared option set. "
        f"Only in {name}: {sorted(actual - shared_option_names())}. "
        f"Missing from {name}: {sorted(shared_option_names() - actual)}. "
        "All three pipeline commands must be stamped from "
        "emuses.cli.pipeline_options.SHARED_PIPELINE_SIGNATURE."
    )


@pytest.mark.parametrize("name", sorted(PIPELINE_COMMANDS))
def test_pipeline_commands_are_not_option_starved(name):
    """The specific regression: a command declaring only its two positional arguments.

    Written as an absolute floor rather than an equality so it keeps failing for the
    original reason even if the shared declaration is later restructured.
    """
    params = set(inspect.signature(PIPELINE_COMMANDS[name]).parameters)

    assert params > {"output_folder", "input_dataset"}, (
        f"`emuses {name}` accepts only {sorted(params)}. Before 2026-08-23 this was true "
        "of umap and heatmap, and it is one of the three reasons neither could run."
    )
    assert len(params) > 20, (
        f"`emuses {name}` exposes {len(params)} options; the shared declaration has "
        f"{len(shared_option_names())}. Something is stamping a reduced signature."
    )


def test_the_shared_declaration_is_the_only_copy():
    """The declaration function must be the sole source, not one list among several.

    If someone re-inlines the options into a command, that command's signature object
    stops being the shared one and this fails - which is the drift the whole file guards.
    """
    for name, command in PIPELINE_COMMANDS.items():
        assert inspect.signature(command) == SHARED_PIPELINE_SIGNATURE, (
            f"`emuses {name}` no longer uses the shared signature object. Decorate it with "
            "@with_pipeline_options instead of declaring its options inline."
        )


# ---------------------------------------------------------------------------------------
# Phase 1C: a command must stay itself on the service-fallback path.
#
# `_umap_async` passes "umap" to the remote service explicitly, but when the service is
# unavailable it falls back to a local path that recovers the pipeline type from
# `config.get("command", "full")`. Nothing set "command", so the fallback silently ran the
# FULL pipeline for `emuses umap` - and then rejected it for having no scores. The bug was
# invisible on the happy path, which is why it needs its own guard.
# ---------------------------------------------------------------------------------------

from emuses.cli.main import _convert_typer_args_to_service_config  # noqa: E402


@pytest.mark.parametrize("command", ["full", "umap", "heatmap"])
def test_config_records_which_command_produced_it(command):
    config = _convert_typer_args_to_service_config(
        command, output_folder=Path("/tmp/out"), input_dataset=Path("/tmp/in")
    )

    assert config["command"] == command, (
        f"config for `emuses {command}` reports command={config.get('command')!r}. "
        "The service-fallback path reads this key to decide which pipeline to run."
    )


@pytest.mark.parametrize("command", ["umap", "heatmap"])
def test_fallback_does_not_turn_a_stage_command_into_full(command):
    """Reproduces the recovery step exactly, on a real config."""
    config = _convert_typer_args_to_service_config(
        command, output_folder=Path("/tmp/out"), input_dataset=Path("/tmp/in")
    )

    # This is the line the fallback executes (emuses/cli/main.py, _execute_via_unified_service).
    pipeline_type = config.get("command", "full")

    assert pipeline_type == command, (
        f"falling back from `emuses {command}` resolves to {pipeline_type!r}, so the "
        "wrong pipeline runs whenever the service is unavailable."
    )


def test_retired_prediction_stage_is_not_advertised():
    """PredictionStage no longer exists; three places used to offer it anyway.

    Accepting a stage name nothing can run turns a typo into a confusing runtime failure
    instead of an immediate, accurate rejection.
    """
    # The lists themselves are allowed to grow - "inference" joined valid_types in Phase 1F.
    # What must not come back is "prediction", so the assertion is about membership rather
    # than an exact literal, which would fail on every legitimate addition instead.
    declarations = {
        "emuses/foundation_fastapi_service/app.py": "valid_stages = [",
        "emuses/cli/service_client.py": "valid_types = [",
    }
    for relative, prefix in declarations.items():
        source = (PROJECT_ROOT / relative).read_text()
        assert prefix in source, (
            f"{relative} no longer declares a stage list starting {prefix!r}. If it moved, "
            "update this test - but do not re-add \"prediction\"."
        )
        for start in _find_all(source, prefix):
            declared = source[start + len(prefix): source.index("]", start)]
            assert "prediction" not in declared, (
                f"{relative} advertises a retired \"prediction\" stage: {declared!r}. "
                "Nothing can run it, so accepting the name turns a typo into a confusing "
                "runtime failure instead of an immediate rejection."
            )

    main_source = (PROJECT_ROOT / "emuses/cli/main.py").read_text()
    assert '"prediction": "PredictionStage"' not in main_source, (
        "emuses/cli/main.py maps a stage name onto PredictionStage, which is retired."
    )
