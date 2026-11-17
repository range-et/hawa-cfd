"""Independent lifecycle and plotting oracles; executor never touches a device."""
from copy import deepcopy

import pytest

from hawa.sweeps import SweepController, plot_segments, validate_candidates


def candidate(number=0):
    return dict(candidate_id='candidate-' + str(number), angle_deg=float(number),
                speed_m_s=3., geometry_hash='geometry-' + str(number), case_hash='case-' + str(number))


def result(c=None, generation=7):
    c = candidate() if c is None else c
    return dict(identity={**{k: c[k] for k in ('candidate_id', 'geometry_hash', 'case_hash')},
                          'generation': generation, 'case_id': 'case', 'revision': 2},
                quality='accepted', window_valid=True, stationarity_passed=True,
                coefficients=dict(CL=2., CD=1.))


class Executor:
    def __init__(self):
        self.calls = []
        self.reply = dict(state='running', candidate_id='candidate-0', generation=7)
        self.errors = {}
        self.closed = True

    def call(self, name, *args):
        self.calls.append((name, args))
        if self.errors.get(name):
            raise RuntimeError(name + ' injected')

    def start(self, descriptor, generation):
        self.call('start', descriptor, generation)
        return descriptor['candidate_id']

    def poll(self, handle):
        self.call('poll', handle)
        return self.reply

    def pause(self, handle):
        self.call('pause', handle)

    def resume(self, handle):
        self.call('resume', handle)

    def cancel(self, handle):
        self.call('cancel', handle)

    def close(self, handle):
        self.call('close', handle)
        return self.closed


def controller(count=2):
    ex = Executor()
    return SweepController([candidate(i) for i in range(count)], ex, 7), ex


def complete(ex, number=0, **changes):
    ex.reply = dict(state='completed', candidate_id=candidate(number)['candidate_id'],
                    generation=7, result=result(candidate(number)), **changes)


@pytest.mark.parametrize('items', [[], [candidate()] * 65, (), None, [candidate(), candidate()], [3]])
def test_invalid_collection(items):
    with pytest.raises(ValueError):
        validate_candidates(items)


@pytest.mark.parametrize('key,value', [('angle_deg', True), ('angle_deg', '2'), ('angle_deg', float('nan')),
                                     ('speed_m_s', 0), ('speed_m_s', float('inf')),
                                     ('speed_m_s', False), ('speed_m_s', '3'),
                                     ('candidate_id', ''), ('candidate_id', '  '), ('candidate_id', 3),
                                     ('geometry_hash', ''), ('geometry_hash', ' '), ('case_hash', ''),
                                     ('case_hash', ' '), ('unknown', 1)])
def test_invalid_candidate(key, value):
    c = candidate()
    c[key] = value
    with pytest.raises(ValueError):
        validate_candidates([c])


def test_validate_copies_and_accepts_limits():
    original = [candidate(i) for i in range(64)]
    frozen = validate_candidates(original)
    original[0]['angle_deg'] = 99
    assert frozen[0]['angle_deg'] == 0
    assert len(frozen) == 64


@pytest.mark.parametrize('generation', [-1, True, 1., '1'])
def test_generation_rejects(generation):
    with pytest.raises(ValueError, match='Generation'):
        SweepController([candidate()], Executor(), generation)


def test_executor_contract():
    with pytest.raises(ValueError, match='start'):
        SweepController([candidate()], object())


def test_ordered_completion_and_idle_reopen():
    c, ex = controller()
    c.tick()
    assert c.state == 'idle' and not ex.calls
    saved = c.save()
    saved[0]['angle_deg'] = 99
    assert c.save()[0]['angle_deg'] == 0
    c.run()
    c.tick()  # start, not poll
    assert [name for name, _ in ex.calls] == ['start']
    snapshot = c.records
    snapshot[0]['state'] = 'failed'
    assert c.records[0]['state'] == 'running'
    complete(ex)
    c.tick()  # observe terminal; handle still owned
    assert c.records[0]['state'] == 'running'
    ex.closed = False
    c.tick()
    assert c.cleanup_error == 'cleanup pending'
    assert [name for name, _ in ex.calls].count('start') == 1
    ex.closed = None
    c.tick()
    assert c.records[0]['state'] == 'completed' and c.cleanup_error is None
    ex.reply['result']['coefficients']['CL'] = 99
    assert c.records[0]['result']['coefficients']['CL'] == 2
    c.tick()
    complete(ex, 1)
    c.tick()
    c.tick()
    c.tick()
    c.run()
    c.tick()
    assert c.state == 'completed'
    assert [name for name, _ in ex.calls].count('start') == 2
    assert [r['candidate']['candidate_id'] for r in c.records] == ['candidate-0', 'candidate-1']
    reopened = SweepController(c.save(), Executor(), 8)
    reopened.tick()
    assert reopened.state == 'idle'
    assert all(r['state'] == 'queued' for r in reopened.records)


def test_pause_before_start_and_while_running_resume_via_run():
    c, ex = controller()
    c.pause()
    c.tick()
    assert not ex.calls and c.state == 'paused'
    c.run()
    c.tick()
    c.pause()
    ex.reply['state'] = 'paused'
    c.tick()
    assert c.records[0]['state'] == 'paused'
    c.resume()
    c.resume()  # idempotent
    assert [name for name, _ in ex.calls].count('resume') == 1
    assert c.state == 'running'


@pytest.mark.parametrize('terminal', ['failed', 'cancelled', 'rejected'])
def test_executor_terminal_states_and_reasons(terminal):
    c, ex = controller(1)
    c.run(); c.tick()
    ex.reply.update(state=terminal, reason='reported reason')
    c.tick(); c.tick()
    assert c.records[0]['state'] == terminal
    assert c.records[0]['reason'] == 'reported reason'
    assert c.state == 'completed'


def test_terminal_default_reason():
    c, ex = controller(1)
    c.run(); c.tick()
    ex.reply['state'] = 'failed'
    c.tick(); c.tick()
    assert c.records[0]['reason'] == 'Executor failed'


@pytest.mark.parametrize('change', [{'candidate_id': 'old'}, {'generation': 6}])
def test_stale_callback_cannot_publish_or_advance(change):
    c, ex = controller()
    c.run(); c.tick()
    complete(ex)
    ex.reply.update(change)
    c.tick(); c.tick()
    assert c.records[0]['state'] == 'running'
    assert [name for name, _ in ex.calls].count('start') == 1
    complete(ex)
    c.tick(); c.tick()
    assert c.records[0]['state'] == 'completed'


@pytest.mark.parametrize('path,value', [(('identity', 'candidate_id'), 'wrong'),
                                       (('identity', 'case_hash'), 'wrong'),
                                       (('identity', 'geometry_hash'), 'wrong'),
                                       (('identity', 'generation'), 8),
                                       (('identity', 'revision'), True),
                                       (('identity', 'case_id'), ''),
                                       (('identity', 'unknown'), 'x'),
                                       (('coefficients', 'CL'), float('nan')),
                                       (('coefficients', 'CD'), float('inf')),
                                       (('coefficients', 'CL'), True),
                                       (('coefficients', 'CD'), '2'),
                                       (('window_valid',), 1),
                                       (('stationarity_passed',), 'yes'),
                                       (('unknown',), 0)])
def test_malformed_completion_fails_and_cleans(path, value):
    c, ex = controller(1)
    c.run(); c.tick()
    complete(ex)
    target = ex.reply['result']
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    c.tick(); c.tick()
    assert c.records[0]['state'] == 'failed'
    assert 'poll/result failed' in c.records[0]['reason']
    assert [name for name, _ in ex.calls][-2:] == ['cancel', 'close']


@pytest.mark.parametrize('change,reason', [({'quality': 'warning'}, 'quality'),
                                         ({'quality': 'rejected'}, 'quality'),
                                         ({'window_valid': False}, 'window'),
                                         ({'stationarity_passed': False}, 'stationarity')])
def test_completed_but_unusable_is_rejected(change, reason):
    c, ex = controller(1)
    c.run(); c.tick()
    complete(ex)
    ex.reply['result'].update(change)
    c.tick(); c.tick()
    assert c.records[0]['state'] == 'rejected'
    assert reason in c.records[0]['reason']
    assert plot_segments(c.records) == []


@pytest.mark.parametrize('reply', [None, {}, dict(state='complete', candidate_id='candidate-0', generation=7),
                                  dict(state='running', candidate_id='candidate-0', generation=True)])
def test_invalid_poll_payload(reply):
    c, ex = controller(1)
    c.run(); c.tick()
    ex.reply = reply
    c.tick(); c.tick()
    assert c.records[0]['state'] == 'failed'


@pytest.mark.parametrize('operation', ['start', 'poll', 'pause', 'resume'])
def test_executor_failure_becomes_failed_record(operation):
    c, ex = controller(1)
    ex.errors[operation] = True
    c.run(); c.tick()
    if operation == 'pause':
        c.pause()
    elif operation == 'resume':
        c.pause(); c.resume()
    elif operation == 'poll':
        c.tick()
    c.tick()
    assert c.records[0]['state'] == 'failed'
    assert operation in c.records[0]['reason']


def test_start_requires_handle(monkeypatch):
    c, ex = controller(1)
    monkeypatch.setattr(ex, 'start', lambda *args: None)
    c.run(); c.tick()
    assert c.records[0]['state'] == 'failed'
    assert 'resource handle' in c.records[0]['reason']


def test_cancel_before_start_and_dispose_are_idempotent():
    c, ex = controller()
    c.cancel(); c.cancel(); c.pause(); c.resume(); c.tick()
    assert c.state == 'cancelled'
    assert all(r['state'] == 'cancelled' for r in c.records)
    with pytest.raises(ValueError, match='new controller'):
        c.run()
    c.dispose(); c.dispose(); c.cancel(); c.tick()
    assert c.state == 'disposed' and not ex.calls


def test_cancel_retains_ownership_until_cancel_and_close_succeed():
    c, ex = controller()
    c.run(); c.tick()
    c.cancel()
    assert c.state == 'draining' and c.records[1]['state'] == 'cancelled'
    ex.errors['cancel'] = True
    c.tick()
    assert 'cancel failed' in c.cleanup_error
    ex.errors['cancel'] = False
    ex.errors['close'] = True
    c.tick()
    assert 'close failed' in c.cleanup_error and c.state == 'draining'
    ex.errors['close'] = False
    ex.closed = 3
    c.tick()
    assert 'close must return' in c.cleanup_error
    ex.closed = True
    c.tick(); c.tick()
    assert c.state == 'cancelled'
    assert all(r['state'] == 'cancelled' for r in c.records)
    assert [name for name, _ in ex.calls].count('cancel') == 2
    assert [name for name, _ in ex.calls].count('start') == 1


def test_dispose_during_pending_completion_drains_without_overwriting_result():
    c, ex = controller()
    c.run(); c.tick()
    complete(ex)
    c.tick(); c.pause(); c.resume(); c.dispose(); c.tick()
    assert c.records[0]['state'] == 'completed'
    assert c.records[1]['state'] == 'cancelled'
    assert c.state == 'disposed'


def test_plot_segments_preserve_gaps_ids_and_provenance():
    records = [dict(candidate=candidate(i), generation=7, state='completed', result=result(candidate(i))) for i in range(4)]
    records[1].update(state='failed', result=None)
    segments = plot_segments(records)
    assert [[point['x'] for point in segment] for segment in segments] == [[0.], [2., 3.]]
    assert [p['y'] for p in segments[1]] == [2., 2.]
    assert segments[1][0]['candidate']['candidate_id'] == 'candidate-2'
    assert segments[1][0]['identity']['revision'] == 2
    segments[0][0]['candidate']['case_hash'] = 'changed'
    assert records[0]['candidate']['case_hash'] == 'case-0'
    assert plot_segments(records, 'cd_alpha')[0][0]['y'] == 1
    assert plot_segments(records, 'cl_cd')[0][0]['x'] == 1
    with pytest.raises(ValueError, match='Plot'):
        plot_segments(records, 'bad')
    records[0]['result']['quality'] = 'warning'
    records[2]['result']['identity']['case_hash'] = 'wrong'
    records[3]['result'] = None
    assert plot_segments(records) == []
    assert plot_segments([]) == []


@pytest.mark.parametrize('generation', [8, True, -1])
def test_plot_rejects_mismatched_or_invalid_record_generation(generation):
    record = dict(candidate=candidate(), generation=generation, state='completed', result=result())
    assert plot_segments([record]) == []
