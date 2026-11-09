"""Compare Rhino-generated sphere wall data on CPU/MPS; run geometry check first."""
import json
from pathlib import Path
import numpy as np
import torch
from hawa.plugin import Session

root = Path(__file__).resolve().parents[1] / 'results/v05/boundaries'
report = {'state': 'running', 'steps': 40, 'rows': []}
path = root / 'sphere-parity.json'
path.write_text(json.dumps(report))
try:
    assert json.loads((root / 'geometry.json').read_text())['state'] == 'completed'
    if not torch.backends.mps.is_available():
        raise RuntimeError('MPS hardware unavailable; comparison is blocked')
    for n in (13, 25, 49):
        case = json.loads((root / ('sphere-%d.json' % n)).read_text())
        arrays = []
        for device in ('cpu', 'mps'):
            session = Session(case, device)
            session.advance(40)
            f = session.flow.f.detach().cpu().numpy().copy()
            assert np.isfinite(f).all()
            arrays.append(f)
            del session
        np.testing.assert_allclose(arrays[0], arrays[1], rtol=3e-4, atol=2e-6)
        report['rows'].append({'shape': case['shape'], 'links': len(case['wall_links']),
                               'max_population_difference': float(np.max(np.abs(arrays[0]-arrays[1])))})
    report['state'] = 'completed'
except Exception as error:
    report.update(state='failed', error=str(error))
    raise
finally:
    path.write_text(json.dumps(report, indent=2)+'\n')
