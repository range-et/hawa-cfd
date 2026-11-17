"""The shipped example is real restart state, not an illustrative field dump."""
from pathlib import Path

import numpy as np

from hawa.native_data import read_archive, restore
from hawa.plugin import Session


def test_shipped_example_restores_paused_and_continues_consistently():
    path = Path(__file__).resolve().parents[1] / 'examples/native-prototype/34-block-at-60.npz'
    populations, metadata, means = read_archive(path)
    assert metadata['iteration'] == 60
    assert metadata['case']['shape'] == [17, 13, 9]
    assert metadata['source_state'] == 'completed'
    assert metadata['absolute_time'] == metadata['local_time']
    fresh = Session(metadata['case'], 'cpu')
    resumed = Session(metadata['case'], 'cpu')
    try:
        restore(fresh, populations, metadata, means)
        restore(resumed, populations, metadata, means)
        np.testing.assert_array_equal(resumed.flow.f.numpy(), populations)
        assert resumed.state == 'paused' and resumed.flow.i == 60
        before = resumed.flow.f.numpy().copy()
        resumed.fields()
        np.testing.assert_array_equal(before, resumed.flow.f.numpy())
        resumed.advance(60)
        fresh.advance(30)
        fresh.advance(30)
        np.testing.assert_array_equal(resumed.flow.f.numpy(), fresh.flow.f.numpy())
        assert resumed.flow.i == fresh.flow.i == 120
        assert resumed.initial_mass == fresh.initial_mass
    finally:
        resumed.pause()
        fresh.pause()
