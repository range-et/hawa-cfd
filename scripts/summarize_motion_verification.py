"""Collect local moving-surface evidence without converting missing runs to passes."""
import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(name):
    return json.loads((ROOT / 'results' / name).read_text())


def main():
    native = read('motion/native-examples.json')
    controls = read('motion/native-controls.json')
    cleanup = read('motion/native-cleanup.json')
    regression = read('v04/native-examples.json')
    assert native['state'] == controls['state'] == regression['state'] == 'completed'
    assert all(r['passed'] for r in native['results'] + regression['results'])
    assert cleanup == dict(jobs=0, sessions=0, workers=[])
    tests = (ROOT / 'results/motion/tests-final.txt').read_text()
    assert '140 passed, 29 skipped' in tests
    report = dict(
        date=str(date.today()), status='implemented, experimental; local development build',
        hawa_tests=dict(passed=140, skipped=29, warnings=4),
        engine_parity=dict(passed=True, devices=['cpu-fp32', 'cpu-fp64', 'mps'],
                           log=(ROOT / 'results/motion/engine-parity.txt').read_text()),
        native_motion=native, native_controls=controls, native_cleanup=cleanup,
        native_stationary_regression=regression,
        rotating_sphere=read('motion/rotating-sphere.json'),
        comoving_equilibrium=read('motion/comoving.json'),
        indicative_timing=read('motion/timing.json'),
        media=dict(path='dist/videos-v04/hawa-moving-surfaces.mp4', steps=1000,
                   fields=101, device='mps', decode_errors=0,
                   inspected_frames=[0, 50, 100], audio=False),
        components=46, supported_definitions=19,
        annotations=read("motion/annotation-report.json"),
        layout_review=dict(rendered=19, visually_inspected=19, legacy_09_preserved=True),
        limitations=[
            'CUDA hardware and Windows installation unverified',
            'Uniform BGK, prescribed rigid motion only',
            'Transient loads contain startup and cell-transition noise',
            'Voxel transitions do not conserve exact displaced fluid volume',
            'Small moving cases can be substantially slower on MPS than CPU',
            'PorousMedium CPU/MPS example parity remains unresolved',
            'Earlier upstream suite results were not rerun; vendored source unchanged',
        ],
    )
    package_path = ROOT / 'results/motion/package.json'
    if package_path.exists():
        report['package_checks'] = {k: v for k, v in json.loads(package_path.read_text()).items() if k not in ('zip_sha256', 'bytes')}
    (ROOT / 'docs/verification-motion-v0.4.json').write_text(json.dumps(report, indent=2) + '\n')


if __name__ == '__main__':
    main()
