"""CPU-independent, poll-driven experiment orchestration; no solver or UI ownership.

Executor methods must return promptly. ``close`` returns False while cleanup is
pending, True/None only after resource release. Exceptions retain the handle.
A start failure must leave no resources; successful start transfers one handle.
"""
from copy import deepcopy
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictFloat, StrictInt, StrictStr

from .motion import require_pinned_pydantic

require_pinned_pydantic()


class Payload(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Candidate(Payload):
    candidate_id: StrictStr = Field(min_length=1)
    angle_deg: StrictFloat = Field(allow_inf_nan=False)
    speed_m_s: StrictFloat = Field(gt=0, allow_inf_nan=False)
    geometry_hash: StrictStr = Field(min_length=1)
    case_hash: StrictStr = Field(min_length=1)


class Identity(Payload):
    candidate_id: StrictStr = Field(min_length=1)
    generation: StrictInt = Field(ge=0)
    geometry_hash: StrictStr = Field(min_length=1)
    case_hash: StrictStr = Field(min_length=1)
    case_id: Optional[StrictStr] = Field(default=None, min_length=1)
    revision: Optional[StrictInt] = Field(default=None, ge=0)


class Coefficients(Payload):
    CL: StrictFloat = Field(allow_inf_nan=False)
    CD: StrictFloat = Field(allow_inf_nan=False)


class SweepResult(Payload):
    identity: Identity
    quality: Literal['accepted', 'warning', 'rejected']
    window_valid: StrictBool
    stationarity_passed: StrictBool
    coefficients: Coefficients


class CallbackIdentity(Payload):
    candidate_id: StrictStr = Field(min_length=1)
    generation: StrictInt = Field(ge=0)


class Poll(CallbackIdentity):
    state: Literal['queued', 'running', 'paused', 'completed', 'failed', 'cancelled', 'rejected']
    result: Optional[SweepResult] = None
    reason: StrictStr = ''


def validate_candidates(candidates):
    """Return detached descriptors after bounded, noncoercive validation."""
    if not isinstance(candidates, list) or not 1 <= len(candidates) <= 64:
        raise ValueError('Sweep requires 1..64 candidate descriptors')
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise ValueError('Candidate descriptors must be dictionaries')
        Candidate.model_validate(candidate)
        if any(not candidate[key].strip() for key in ('candidate_id', 'case_hash', 'geometry_hash')):
            raise ValueError('Candidate identities must not be blank')
    if len({c['candidate_id'] for c in candidates}) != len(candidates):
        raise ValueError('Candidate IDs must be unique')
    return deepcopy(candidates)


def _completed_result(result, candidate, generation):
    """Reject completed data until identity and every usability gate agree."""
    SweepResult.model_validate(result)
    identity = result['identity']
    expected = {key: candidate[key] for key in ('candidate_id', 'case_hash', 'geometry_hash')}
    expected['generation'] = generation
    if any(identity[key] != value for key, value in expected.items()):
        raise ValueError('Completed measurement identity mismatch')
    if result['quality'] != 'accepted':
        return 'rejected', 'Measurement quality is ' + result['quality']
    if not result['window_valid']:
        return 'rejected', 'Measurement window is invalid or insufficient'
    if not result['stationarity_passed']:
        return 'rejected', 'Measurement stationarity criterion failed'
    return 'completed', ''


class SweepController:
    """Single-owner state machine. Call tick from a poll loop; never concurrently.

    Cancellation/disposal terminalizes queued candidates and retains an active
    handle until cancel succeeds and close confirms cleanup. ``records`` and
    ``save`` are detached snapshots. Reopening saved descriptors starts idle.
    """
    def __init__(self, candidates, executor, generation=0):
        self._candidates = validate_candidates(candidates)
        if type(generation) is not int or generation < 0:
            raise ValueError('Generation must be a nonnegative integer')
        for method in ('start', 'poll', 'pause', 'resume', 'cancel', 'close'):
            if not callable(getattr(executor, method, None)):
                raise ValueError('Executor requires callable ' + method)
        self._executor = executor
        self.generation = generation
        self._mode = 'idle'
        self._active = None
        self._handle = None
        self._pending = None
        self._needs_cancel = False
        self._records = [dict(candidate=deepcopy(c), generation=generation, state='queued', reason='', result=None)
                         for c in self._candidates]
        self.cleanup_error = None

    @property
    def records(self):
        return deepcopy(self._records)

    @property
    def state(self):
        if self._mode in ('cancelled', 'disposed') and self._handle is not None:
            return 'draining'
        if all(r['state'] in ('completed', 'failed', 'cancelled', 'rejected') for r in self._records):
            return self._mode if self._mode in ('cancelled', 'disposed') else 'completed'
        return self._mode

    def save(self):
        """Persist only configuration, never a live handle or run switch."""
        return deepcopy(self._candidates)

    def run(self):
        if self._mode in ('cancelled', 'disposed'):
            raise ValueError('Create a new controller to restart a stopped sweep')
        if self._mode == 'paused':
            self.resume()
        else:
            self._mode = 'running'

    def _terminal(self, state, reason, result=None, cancel=False):
        self._pending = dict(candidate=deepcopy(self._candidates[self._active]),
                             generation=self.generation, state=state, reason=reason, result=deepcopy(result))
        self._needs_cancel = cancel

    def _control(self, action):
        try:
            getattr(self._executor, action)(self._handle)
        except Exception as exc:
            self._terminal('failed', action + ' failed: ' + str(exc), cancel=True)

    def pause(self):
        if self._mode in ('cancelled', 'disposed'):
            return
        self._mode = 'paused'
        if self._handle is not None and self._pending is None:
            self._control('pause')

    def resume(self):
        if self._mode != 'paused':
            return
        self._mode = 'running'
        if self._handle is not None and self._pending is None:
            self._control('resume')

    def _stop(self, mode):
        if self._mode == 'disposed':
            return
        self._mode = mode
        for index, record in enumerate(self._records):
            if index != self._active and record['state'] == 'queued':
                record.update(state='cancelled', reason='Sweep ' + mode)
        if self._handle is not None and self._pending is None:
            self._terminal('cancelled', 'Sweep ' + mode, cancel=True)

    def cancel(self):
        self._stop('cancelled')

    def dispose(self):
        self._stop('disposed')

    def _drain(self):
        if self._needs_cancel:
            try:
                self._executor.cancel(self._handle)
            except Exception as exc:
                self.cleanup_error = 'cancel failed: ' + str(exc)
                return
            self._needs_cancel = False
        try:
            closed = self._executor.close(self._handle)
            if closed is False:
                self.cleanup_error = 'cleanup pending'
                return
            if closed is not None and closed is not True:
                raise ValueError('close must return True, False or None')
        except Exception as exc:
            self.cleanup_error = 'close failed: ' + str(exc)
            return
        self._records[self._active] = self._pending
        self._handle = self._active = self._pending = None
        self.cleanup_error = None

    def tick(self):
        """Perform at most one start/poll; cleanup occupies a separate tick."""
        if self._pending is not None:
            self._drain()
            return
        if self._handle is not None:
            try:
                reply = self._executor.poll(self._handle)
                if not isinstance(reply, dict):
                    raise ValueError('Poll reply must be a dictionary')
                identity = CallbackIdentity.model_validate({key: reply[key] for key in ('candidate_id', 'generation')})
                candidate = self._candidates[self._active]
                if (identity.candidate_id != candidate['candidate_id'] or
                        identity.generation != self.generation):
                    return  # Old callbacks are not observations of this handle.
                Poll.model_validate(reply)
                state = reply['state']
                if state == 'completed':
                    state, reason = _completed_result(reply.get('result'), candidate, self.generation)
                    self._terminal(state, reason, reply['result'])
                elif state in ('failed', 'cancelled', 'rejected'):
                    self._terminal(state, reply.get('reason') or 'Executor ' + state)
                else:
                    self._records[self._active]['state'] = state
                    self._records[self._active]['reason'] = reply.get('reason', '')
            except Exception as exc:
                self._terminal('failed', 'poll/result failed: ' + str(exc), cancel=True)
            return
        if self._mode != 'running':
            return
        index = next((i for i, r in enumerate(self._records) if r['state'] == 'queued'), None)
        if index is None:
            return
        self._active = index
        try:
            handle = self._executor.start(deepcopy(self._candidates[index]), self.generation)
            if handle is None:
                raise ValueError('start must return a resource handle')
            self._handle = handle
            self._records[index]['state'] = 'running'
        except Exception as exc:
            self._records[index].update(state='failed', reason='start failed: ' + str(exc))
            self._active = None


def plot_segments(records, kind='cl_alpha'):
    """Return ordered identified segments, splitting at every unusable candidate."""
    if kind not in ('cl_alpha', 'cd_alpha', 'cl_cd'):
        raise ValueError('Plot must be cl_alpha, cd_alpha or cl_cd')
    segments, segment = [], []
    for record in records:
        candidate = record['candidate']
        usable = record['state'] == 'completed'
        result = record.get('result')
        if usable:
            try:
                Candidate.model_validate(candidate)
                if type(record['generation']) is not int or record['generation'] < 0:
                    raise ValueError('Invalid record generation')
                state, _ = _completed_result(result, candidate, record['generation'])
                usable = state == 'completed'
            except (ValueError, TypeError, KeyError):
                usable = False
        if not usable:
            if segment:
                segments.append(segment)
                segment = []
            continue
        coefficient = result['coefficients']
        x = coefficient['CD'] if kind == 'cl_cd' else candidate['angle_deg']
        y = coefficient['CD'] if kind == 'cd_alpha' else coefficient['CL']
        segment.append(dict(x=x, y=y, candidate=deepcopy(candidate),
                            identity=deepcopy(result['identity'])))
    if segment:
        segments.append(segment)
    return segments
