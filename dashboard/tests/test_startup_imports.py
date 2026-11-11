"""Startup import contracts, including a pre-Phase-6 module cached by Streamlit."""
import ast
import importlib
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]


class StartupImportTests(unittest.TestCase):
    def test_every_dashboard_import_in_entrypoint_exists_and_is_callable(self):
        tree = ast.parse((ROOT / 'dashboard/app.py').read_text(encoding='utf-8'))
        for statement in tree.body:
            if isinstance(statement, ast.ImportFrom) and statement.module.startswith('dashboard.'):
                module = importlib.import_module(statement.module)
                for imported in statement.names:
                    with self.subTest(module=statement.module, name=imported.name):
                        self.assertTrue(callable(getattr(module, imported.name, None)))

    def test_entrypoint_recovers_pre_phase6_cached_view_module(self):
        views = importlib.import_module('dashboard.data_views')
        # Simulate the existing process's old module without altering source files.
        with patch.dict(views.__dict__):
            del views.__dict__['slot_history']
            namespace = runpy.run_path(str(ROOT / 'dashboard/app.py'), run_name='startup_import_test')
            self.assertTrue(callable(namespace['slot_history']))
            self.assertTrue(callable(namespace['live_feature_record']))
            self.assertTrue(callable(namespace['minute_history']))
            self.assertTrue(callable(namespace['slot_snapshot']))


if __name__ == '__main__':
    unittest.main()
