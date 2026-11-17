"""Terminal state must survive close during the worker's publication interval."""
import threading

import pytest

import hawa.sweep_executor as module
from test_sweep_executor import prepared, finish, wait_for


@pytest.mark.parametrize('terminal', ['completed', 'rejected', 'failed'])
def test_close_preserves_terminal_state_before_details_publication(monkeypatch, terminal):
    """Gate after terminal lock release, before finally can publish retained data."""
    reached, release = threading.Event(), threading.Event()
    original_init = module._Run.__init__

    def initialize(run, entry, generation):
        original_init(run, entry, generation)

        class PublicationCondition(threading.Condition):
            def __exit__(self, *args):
                # Retain real Condition lock/wait/notification semantics. The
                # controller must be free to poll/close while this worker waits.
                result = super().__exit__(*args)
                if (threading.current_thread() is run.thread and
                        run.state == terminal and run.details is None and
                        not reached.is_set()):
                    reached.set()
                    if not release.wait(5):
                        raise RuntimeError('test did not release publication gate')
                return result

        run.condition = PublicationCondition()

    monkeypatch.setattr(module._Run, '__init__', initialize)
    expected_reason = ''
    if terminal == 'rejected':
        expected_reason = 'window intentionally rejected before publication'
        def reject(request, samples):
            raise ValueError(expected_reason)
        monkeypatch.setattr(module, 'summarize', reject)
    elif terminal == 'failed':
        expected_reason = 'solver intentionally failed before publication'
        def fail(session, steps):
            raise RuntimeError(expected_reason)
        monkeypatch.setattr(module.Session, 'advance', fail)

    data = prepared()
    executor = module.CpuSweepExecutor(data)
    handle = executor.start(data['a']['candidate'], 7)
    try:
        wait_for(reached.is_set, executor)
        before = executor.poll(handle)
        assert before['state'] == terminal
        assert before['reason'] == expected_reason
        assert executor.results('a', 7) is None
        assert executor.close(handle) is False
        assert executor.audit()['handles'] == executor.audit()['live_workers'] == 1
        release.set()
        after = finish(executor, handle)
        assert after == before
        retained = executor.results('a', 7)
        assert retained['state'] == terminal
        assert retained['reason'] == expected_reason
        assert retained['identity'] == data['a']['request']['identity']
        assert executor.audit() == dict(handles=0, live_workers=0, session_ids=[])
    finally:
        # Always release the actual worker before closing, even if an assertion
        # or mutated close fails. Never retry cancellation while it is gated.
        release.set()
        wait_for(lambda: not executor.audit()['live_workers'])
        executor.close(handle)
