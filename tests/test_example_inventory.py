"""Verification must not turn absent evidence into a passing parity result."""
import importlib.util
from pathlib import Path
import pytest

spec = importlib.util.spec_from_file_location('example_inventory', Path(__file__).resolve().parents[1] / 'scripts/example_inventory.py')
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


def test_missing_or_partial_reports_rejected(tmp_path):
    with pytest.raises(RuntimeError):
        inventory.require_complete_reports(tmp_path, ['a.py', 'sub/b.ipynb'])
    (tmp_path / 'a.py').mkdir()
    (tmp_path / 'a.py/report.json').write_text('{}')
    with pytest.raises(RuntimeError):
        inventory.require_complete_reports(tmp_path, ['a.py', 'sub/b.ipynb'])
    (tmp_path / 'sub__b.ipynb').mkdir()
    (tmp_path / 'sub__b.ipynb/report.json').write_text('{}')
    inventory.require_complete_reports(tmp_path, ['a.py', 'sub/b.ipynb'])
    with pytest.raises(RuntimeError):
        inventory.require_complete_reports(tmp_path, ['a.py'])
    with pytest.raises(RuntimeError):
        inventory.require_complete_reports(tmp_path, [])


def test_pinned_inventory_has_all_sixteen_entrypoints():
    root = Path(__file__).resolve().parents[1] / 'vendor/lettuce/examples'
    assert len(inventory.entrypoints(root)) == 16
