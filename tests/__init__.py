import unittest
from pathlib import Path


class TestTopLevelExports(unittest.TestCase):
    """Verify that key runtime classes and options resolve from the package namespace."""

    def test_run_csv_repository_reexported(self):
        from classificator import RunCsvRepository

        self.assertTrue(callable(RunCsvRepository))

    def test_word_store_reexported(self):
        from classificator import WordStore

        store = WordStore()
        self.assertIsNotNone(store)

    def test_step1_options_reexported(self):
        from classificator import Step1Options

        opts = Step1Options(output_csv_path=Path("test.csv"))
        self.assertEqual(opts.output_csv_path, Path("test.csv"))

    def test_step2_options_reexported(self):
        from classificator import Step2Options

        opts = Step2Options(run_slug="t", model="x", base_csv_path=Path("base.csv"), output_csv_path=Path("out.csv"))
        self.assertEqual(opts.run_slug, "t")

    def test_capability_state_reexported(self):
        from classificator.lm import CapabilityState

        state = CapabilityState()
        self.assertIsNotNone(state)
        self.assertTrue(state.reasoning_controls_supported)

    def test_lm_package_exports_all_canonical_names(self):
        """Every name in lm.__all__ must resolve to a callable class via top-level import."""
        from classificator.lm import __all__ as exported

        canonical = {"LmStudioClient", "ScoringContext", "CapabilityState"}
        self.assertEqual(set(exported), canonical, f"lm.__all__ drifted: {set(exported)}")
        for name in sorted(canonical):
            cls = getattr(__import__("classificator.lm", fromlist=[name]), name)
            self.assertTrue(callable(cls), f"{name} is not callable")


class TestPackageIntegrity(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        from classificator.batch_size_adapter import BatchSizeAdapter

        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)

    def test_assert_exports_resolved_passes_cleanly(self):
        """Importing the package should leave _assert_exports_resolved intact."""
        from classificator import __all__ as exported

        missing = [n for n in exported if not hasattr(__import__("classificator"), n)]
        self.assertEqual(missing, [], f"Missing exports at import time: {missing}")

    def test_assert_exports_resolved_raises_on_missing_name(self):
        """Patching a bad name into __all__ must trigger ImportError."""
        import classificator as pkg_mod
        from classificator import _assert_exports_resolved

        original = list(pkg_mod.__all__)
        pkg_mod.__all__ = original + ["_nonexistent_fake_export"]

        try:
            with self.assertRaises(ImportError) as ctx:
                _assert_exports_resolved()
            self.assertIn("_nonexistent_fake_export", str(ctx.exception))
        finally:
            pkg_mod.__all__ = tuple(original)


class TestValidateSteps(unittest.TestCase):
    """Tests for steps/__init__.py validation functionality."""

    def test_all_steps_registered(self):
        from classificator.steps import _STEPS

        self.assertEqual(len(_STEPS), 5)

    def test_validate_returns_empty_on_valid_modules(self):
        from classificator.steps import _validate_step_modules

        errors = _validate_step_modules()
        self.assertEqual(errors, [])

    def test_first_param_is_options_for_all_steps(self):
        from inspect import signature

        from classificator.steps import _STEPS

        for name, _, func in _STEPS:
            sig = signature(func)
            params = list(sig.parameters.keys())
            self.assertEqual(params[0], "options", f"{name}: first param must be 'options', got {params}")

    def test_validate_raises_with_invalid_entry(self):
        from classificator.steps import validate_steps as _validate_steps
        from classificator.steps import _STEPS

        original = list(_STEPS)
        modified = []
        for name, label, func in original:
            if name == "step3":
                modified.append((name, label, None))
            else:
                modified.append((name, label, func))

        import classificator.steps as steps_mod

        steps_mod._STEPS = tuple(modified)

        try:
            with self.assertRaises(ValueError):
                _validate_steps()
        finally:
            steps_mod._STEPS = tuple(original)

    def test_validate_returns_errors_for_non_callable(self):
        from classificator.steps import _validate_step_modules as _vm
        from classificator.steps import _STEPS

        original = list(_STEPS)
        modified = [(name, label, 42 if name == "step1" else func) for name, label, func in original]
        import classificator.steps as steps_mod

        steps_mod._STEPS = tuple(modified)

        try:
            errors = _vm()
            self.assertEqual(len(errors), 1)
            self.assertIn("not callable", str(errors[0]))
        finally:
            steps_mod._STEPS = tuple(original)

    def test_validate_detects_wrong_first_parameter(self):
        from unittest.mock import MagicMock

        from classificator.steps import _validate_step_modules as _vm
        from classificator.steps import _STEPS

        fake_func = MagicMock()
        fake_func.__name__ = "fake_run"
        fake_func.__call__.__self__ = None
        fake_sig_params = {"x": 1, "y": 2}
        type(fake_sig_params["x"]).__class__
        import inspect

        fake_func.__signature__ = inspect.Signature(
            [inspect.Parameter("x", inspect.Parameter.POSITIONAL_OR_KEYWORD),
             inspect.Parameter("y", inspect.Parameter.POSITIONAL_OR_KEYWORD)]
        )

        original = list(_STEPS)
        modified = [(name, label, fake_func if name == "step1" else func) for name, label, func in original]
        import classificator.steps as steps_mod

        steps_mod._STEPS = tuple(modified)

        try:
            errors = _vm()
            self.assertEqual(len(errors), 1)
            self.assertIn("options", str(errors[0]))
        finally:
            steps_mod._STEPS = tuple(original)


if __name__ == "__main__":
    unittest.main()
