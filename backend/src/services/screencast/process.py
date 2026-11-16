"""Per-job subprocess tracking for immediate ffmpeg cancellation."""

import os
import signal
import subprocess
import threading

_job_procs: dict[str, list[subprocess.Popen]] = {}
_job_procs_lock = threading.Lock()


def _register_proc(job_uuid: str, proc: subprocess.Popen) -> None:
    with _job_procs_lock:
        _job_procs.setdefault(job_uuid, []).append(proc)


def _unregister_proc(job_uuid: str, proc: subprocess.Popen) -> None:
    with _job_procs_lock:
        procs = _job_procs.get(job_uuid, [])
        try:
            procs.remove(proc)
        except ValueError:
            pass
        # The last process of a job takes the entry along, else every job leaves an empty list behind.
        if not procs:
            _job_procs.pop(job_uuid, None)


def _kill(proc: subprocess.Popen) -> None:
    """Kills the whole process group, the process alone when the group is gone."""
    try:
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def kill_job_procs(job_uuid: str) -> None:
    """Kill all active ffmpeg subprocesses for a job (process group kill)."""
    with _job_procs_lock:
        procs = _job_procs.pop(job_uuid, [])
    for proc in procs:
        _kill(proc)


def run_proc(cmd: list[str], timeout: int, job_uuid: str | None = None) -> subprocess.CompletedProcess:
    """Run a command in a new session (killable process group). Registers with job tracking."""
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        start_new_session=True,
    )
    if job_uuid:
        _register_proc(job_uuid, proc)
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill(proc)
        stdout, stderr = proc.communicate()
    finally:
        # A time limit of the job struck while waiting, the process must not run on alone.
        if proc.poll() is None:
            _kill(proc)
        if job_uuid:
            _unregister_proc(job_uuid, proc)
    return subprocess.CompletedProcess(
        cmd, proc.returncode,
        stdout.decode(errors="replace"),
        stderr.decode(errors="replace"),
    )
