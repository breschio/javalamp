"""Cross-platform sleep guard.

On macOS we spawn ``caffeinate -d -i`` while a context is active so the
display won't sleep and the system won't idle-sleep. On other platforms
this is a no-op (with hooks left in for a future Linux/Windows port).
"""

from __future__ import annotations

import contextlib
import logging
import shutil
import signal
import subprocess
import sys
from typing import Iterator, Optional

log = logging.getLogger(__name__)


@contextlib.contextmanager
def keep_awake(enabled: bool = True) -> Iterator[Optional[subprocess.Popen]]:
    """Context manager: prevent display sleep while inside the block.

    Yields the underlying Popen on macOS (or None elsewhere / when disabled).
    Always cleans up the subprocess on exit, including on exception.
    """
    if not enabled:
        yield None
        return

    proc: Optional[subprocess.Popen] = None
    if sys.platform == "darwin":
        if shutil.which("caffeinate") is None:
            log.info("caffeinate binary not found; sleep guard disabled")
            yield None
            return
        try:
            proc = subprocess.Popen(
                ["caffeinate", "-d", "-i"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                # New process group so a Ctrl+C in the foreground tty
                # doesn't kill us before we get a chance to clean up.
                preexec_fn=_detach_from_signals,
            )
        except OSError as e:
            log.warning("Failed to spawn caffeinate: %s", e)
            proc = None
    else:
        # TODO: Linux (`systemd-inhibit --what=idle:sleep`) and
        # Windows (`SetThreadExecutionState`) hooks go here.
        log.info("Sleep guard not implemented for platform=%s", sys.platform)

    try:
        yield proc
    finally:
        if proc is not None and proc.poll() is None:
            try:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait(timeout=1)
            except ProcessLookupError:
                pass


def _detach_from_signals() -> None:
    """Ignore SIGINT in the child so Ctrl+C reaches Python instead."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)
