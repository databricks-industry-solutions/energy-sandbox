"""Smoke tests for Pipeline Commander app."""
from pathlib import Path


class TestAppStructure:
    def test_requirements_exist(self):
        req = Path(__file__).resolve().parent.parent / "app" / "requirements.txt"
        assert req.exists()

    def test_app_yaml_exists(self):
        assert (Path(__file__).resolve().parent.parent / "app.yaml").exists()

    def test_databricks_yml_exists(self):
        assert (Path(__file__).resolve().parent.parent / "databricks.yml").exists()
