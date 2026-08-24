"""The registry accepts what the pipeline actually produces.

This is the contract the 50-odd failures in this directory were really about.
Their fixtures built a directory containing a bare sklearn ``Pipeline`` and
expected ``install_model`` to accept it. ADR 2.1 says an EMUSES model is an
entire output folder and that components are not separable, so the registry was
correct to refuse and the fixtures were obsolete.

Rather than assert that against a hand-made folder - which only tests the
validator against someone's idea of the format - these run against a folder a
real pipeline run produced. If the pipeline's output format and the registry's
expectations ever drift apart, this fails, and it fails on the real
disagreement rather than on a stale fixture.
"""

from emuses.tools.local_model_registry import LocalModelRegistry
from emuses.tools.model_io import ModelIOManager


class TestRealModelInstallation:
    @staticmethod
    def _io_manager(tmp_path):
        """ModelIOManager's base_path is its own metadata store, not the model."""
        return ModelIOManager(base_path=tmp_path / "io_manager")

    def test_pipeline_output_validates_as_a_complete_model(self, real_emuses_model, tmp_path):
        validation = self._io_manager(tmp_path).validate_model(real_emuses_model)

        assert validation.is_complete_model, (
            f"A real pipeline run produced a folder the registry rejects: "
            f"{validation.validation_errors}"
        )
        assert validation.type == "emuses_model"

    def test_install_succeeds_and_the_model_is_retrievable(self, real_emuses_model, tmp_path):
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        result = registry.install_model(real_emuses_model)

        assert result["status"] == "success", (
            f"install_model refused a genuine pipeline output: {result}"
        )

        model_id = result["model_id"]
        listed = registry.list_models()
        assert any(m["model_id"] == model_id for m in listed), (
            "install_model reported success but the model is not listed"
        )

        # The point of the registry: hand back a path that is still a valid model.
        resolved = registry.get_model_path(model_id)
        assert resolved is not None
        assert self._io_manager(tmp_path).validate_model(resolved).is_complete_model, (
            "The registry stored the model but what it hands back no longer "
            "validates - installation is not round-tripping the folder intact."
        )

    def test_the_name_defaults_to_the_folder_name(self, real_emuses_model, tmp_path):
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        result = registry.install_model(real_emuses_model)

        assert result["status"] == "success"
        info = registry.get_model_info(result["model_id"])
        assert info["name"] == real_emuses_model.name


class TestInstallForceFlag:
    """`--force` is documented as bypassing duplicate detection.

    It was not doing so. `models_commands.install` calls
    ``install_model_with_deduplication(model_path=..., model_name=..., force=force)``,
    but that method's signature is ``(model_path, skip_duplicates, transaction,
    **kwargs)`` - there is no ``force`` parameter. The argument landed in
    ``**kwargs``, was forwarded to ``install_model``, which does not read
    ``kwargs`` either, and was dropped. ``skip_duplicates`` kept its default of
    True, so a second install of the same folder was skipped whether or not the
    user passed ``--force``.

    ``--name`` is unaffected and always worked: it forwards through the same
    ``**kwargs`` but lands on ``install_model``'s real ``model_name`` parameter.
    """

    def test_second_install_is_skipped_as_a_duplicate_by_default(
        self, real_emuses_model, tmp_path
    ):
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        first = registry.install_model_with_deduplication(model_path=real_emuses_model)
        assert first["status"] == "success"

        second = registry.install_model_with_deduplication(model_path=real_emuses_model)
        assert second["status"] != "success", (
            "Installing an identical folder twice should be detected as a duplicate"
        )

    def test_force_bypasses_duplicate_detection(self, real_emuses_model, tmp_path):
        """The regression test for the dropped flag.

        Exercised through the same call the CLI makes, so it fails if the CLI
        stops translating --force into skip_duplicates.
        """
        registry = LocalModelRegistry(registry_path=tmp_path / "registry")

        first = registry.install_model_with_deduplication(model_path=real_emuses_model)
        assert first["status"] == "success"

        forced = registry.install_model_with_deduplication(
            model_path=real_emuses_model, skip_duplicates=False
        )
        assert forced["status"] == "success", (
            f"skip_duplicates=False should install anyway, got: {forced}"
        )

    def test_cli_install_passes_force_through_to_the_registry(self, monkeypatch):
        """--force must reach skip_duplicates, not vanish into **kwargs."""
        from typer.testing import CliRunner

        from emuses.cli import models_commands

        captured = {}

        class FakeRegistry:
            def install_model_with_deduplication(self, **kwargs):
                captured.update(kwargs)
                return {"status": "success", "model_id": "x", "name": "x",
                        "model_type": "emuses_model"}

        monkeypatch.setattr(
            models_commands.ModelRegistryFactory,
            "create_registry",
            staticmethod(lambda *a, **k: FakeRegistry()),
            raising=False,
        )

        result = CliRunner().invoke(
            models_commands.models_app, ["install", ".", "--force"]
        )

        assert "force" not in captured, (
            "The CLI passed force= straight through; install_model_with_deduplication "
            f"has no such parameter and drops it. Captured: {captured}"
        )
        assert captured.get("skip_duplicates") is False, (
            "--force must translate into skip_duplicates=False. "
            f"Captured: {captured}, CLI output: {result.output}"
        )
