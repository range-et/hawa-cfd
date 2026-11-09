"""The executable upstream example inventory shared by runner and verifier."""


def entrypoints(root):
    return sorted(p for p in root.rglob('*') if p.suffix == '.ipynb' or (
        p.suffix == '.py' and p.name != '__init__.py' and
        (p.parent == root or p.parent.name == 'advanced_flows' or
         p.name == '01_script_cylinder_simulation.py')))


def require_complete_reports(root, expected):
    """Fail closed on absent, extra, or partial example output directories."""
    found = {p.parent.name for p in root.glob('*/report.json')}
    expected = {name.replace('/', '__') for name in expected}
    if not expected or found != expected:
        raise RuntimeError('Incomplete example reports in {}: missing={}, extra={}'.format(
            root, sorted(expected - found), sorted(found - expected)))
