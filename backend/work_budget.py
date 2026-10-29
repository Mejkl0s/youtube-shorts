"""Cooperative job limits with termination of owned subprocess trees."""
from contextvars import ContextVar
from functools import wraps
import os
import signal
import subprocess
import threading
import time


SEARCH_SECONDS = 300
_active = ContextVar('studio_work_budget', default=None)
_controls = {}
_lock = threading.Lock()


class WorkStopped(RuntimeError):
    def __init__(self, cancelled=False):
        self.cancelled = cancelled
        super().__init__('Hledání bylo zastaveno.' if cancelled else 'Hledání překročilo časový limit pěti minut.')


class Budget:
    def __init__(self, seconds=SEARCH_SECONDS):
        self.started = time.monotonic()
        self.seconds = seconds
        self.cancel = threading.Event()
        self.cache = {}
        self.unavailable_engines = set()
        self.label = None

    def check(self):
        if self.cancel.is_set():
            raise WorkStopped(True)
        if time.monotonic()-self.started >= self.seconds:
            raise WorkStopped()

    def remaining(self):
        self.check()
        return max(.01, self.seconds-(time.monotonic()-self.started))


def current():
    return _active.get()


def checkpoint():
    if budget := current():
        budget.check()


def timeout(seconds):
    return min(seconds, budget.remaining()) if (budget := current()) else seconds


def stage(message):
    checkpoint()
    if (budget := current()) and budget.label:
        budget.label(message)


def reserve(job_id):
    with _lock:
        return _controls.setdefault(job_id, Budget())


def cancel(job_id):
    with _lock:
        budget = _controls.get(job_id)
        if budget:
            budget.cancel.set()
        return budget is not None


def cancel_all():
    with _lock:
        for budget in _controls.values():
            budget.cancel.set()


def timing(job_id):
    with _lock:
        budget = _controls.get(job_id)
    if not budget:
        return {}
    elapsed = time.monotonic()-budget.started
    return {'elapsed_seconds': round(elapsed, 1), 'limit_seconds': budget.seconds,
            'remaining_seconds': max(0, round(budget.seconds-elapsed, 1)),
            'cancel_requested': budget.cancel.is_set()}


def limited_discovery(fn):
    @wraps(fn)
    def wrapped(job_id, *args, **kwargs):
        from . import main as m
        budget = reserve(job_id)
        budget.label = lambda text: m.set_job(job_id, message=text)
        token = _active.set(budget)
        try:
            checkpoint()
            return fn(job_id, *args, **kwargs)
        except WorkStopped as error:
            m.set_job(job_id, status='failed', progress=100, cancelled=error.cancelled, message=str(error))
        finally:
            details = timing(job_id)
            _active.reset(token)
            with _lock:
                _controls.pop(job_id, None)
            if job_id in m.jobs:
                m.set_job(job_id, **details)
    return wrapped


def _terminate(process):
    if os.name == 'nt':
        # Terminate only this job's owned tree (yt-dlp may launch FFmpeg/Node).
        try:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, timeout=3)
        except (OSError, subprocess.TimeoutExpired):
            pass
        if process.poll() is None:
            process.kill()
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        process.communicate(timeout=3)
    except subprocess.TimeoutExpired:
        for stream in (process.stdout, process.stderr):
            if stream:
                stream.close()


def process_result(args, seconds):
    budget = current()
    if not budget:
        return subprocess.run(args, capture_output=True, timeout=seconds)
    budget.check()
    deadline = time.monotonic()+min(seconds, budget.remaining())
    options = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == 'nt' else {'start_new_session': True}
    process = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **options)
    try:
        while True:
            budget.check()
            remaining = deadline-time.monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(args, seconds)
            try:
                out, err = process.communicate(timeout=min(.2, remaining))
                budget.check()
                return subprocess.CompletedProcess(args, process.returncode, out, err)
            except subprocess.TimeoutExpired:
                if time.monotonic() >= deadline:
                    budget.check()
                    raise subprocess.TimeoutExpired(args, seconds)
    except BaseException:
        _terminate(process)
        raise
