"""Windows checkout normalization must not hide substantive upstream edits."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    'audit_backport', Path(__file__).resolve().parents[1] / 'scripts/audit_backport.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def test_crlf_checkout_passes_but_source_and_test_changes_fail(tmp_path, monkeypatch):
    source = tmp_path / 'lettuce/nested/module.py'
    test = tmp_path / 'tests/test_original.py'
    for path in (source, test):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'value = 1\r\n')
    digest = hashlib.sha256(b'value = 1\n').hexdigest()
    (tmp_path / 'upstream.json').write_text(json.dumps({
        'commit': 'test', 'source_sha256': {'lettuce/nested/module.py': digest},
        'test_sha256': {'tests/test_original.py': digest}}))
    monkeypatch.setattr(audit, 'VENDOR', tmp_path)
    assert audit.audit()['unchanged_test_files'] == 1
    source.write_bytes(b'value = 2\r\n')
    with pytest.raises(RuntimeError, match='Unreviewed source changes'):
        audit.audit()
    source.write_bytes(b'value = 1\r\n')
    test.write_bytes(b'value = 2\r\n')
    with pytest.raises(RuntimeError, match='Original upstream test modified'):
        audit.audit()
    test.write_bytes(b'value = 1\r\n')
    (source.parent / 'extra.py').write_text('')
    with pytest.raises(RuntimeError, match='extra.py'):
        audit.audit()
