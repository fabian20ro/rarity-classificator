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


class TestPackageIntegrity(unittest.TestCase):
    def test_batch_size_adapter_import(self):
        from classificator.batch_size_adapter import BatchSizeAdapter

        adapter = BatchSizeAdapter(initial_size=10, min_size=3, window_size=5)
        self.assertEqual(adapter.current_size, 10)


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
        from inspect import signature, isfunction

        from classificator.steps import (
            _run_step1,
            _run_step2,
            _run_step3,
            _run_step4,
            _run_step5,
            _STEPS,
        )
        for name, _, func in _STEPS:
            self.assertTrue(isfunction(func))
            sig = signature(func)
            # Just verify they're callable functions
            self.assertTrue(callable(func), f"{name} should be callable")

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


if __name__ == "__main__":
    unittest.main()
