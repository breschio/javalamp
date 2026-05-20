"""Non-blocking single-key reader with arrow / escape sequence handling.

Used by both the picker and the main scene runner. Returns named strings
("up", "down", "left", "right", "esc", "enter") for special keys, and
the raw decoded character otherwise.
"""

from __future__ import annotations

import os
import select
import sys
import termios
import tty
from contextlib import contextmanager
from typing import Iterator, Optional


@contextmanager
def cbreak_stdin() -> Iterator[Optional[int]]:
    """Put stdin into cbreak mode for the duration of the block.

    Yields the fd if stdin is a tty we could put in cbreak mode, else None
    (e.g. piped input, dumb terminal). Restores original termios on exit.
    """
    if not sys.stdin.isatty():
        yield None
        return
    fd = sys.stdin.fileno()
    try:
        old = termios.tcgetattr(fd)
    except termios.error:
        yield None
        return
    try:
        tty.setcbreak(fd)
        yield fd
    finally:
        try:
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        except termios.error:
            pass


def read_key(fd: Optional[int]) -> Optional[str]:
    """Read at most one logical key. Returns:

    - None             — no key pending
    - "up"/"down"/"left"/"right" — arrow keys (CSI sequences)
    - "esc"            — bare ESC or unrecognized escape sequence
    - "enter"          — Enter key (\r or \n)
    - "\x03"           — Ctrl-C (callers usually treat this as quit)
    - any other 1-char string — the typed character
    """
    if fd is None:
        return None
    r, _, _ = select.select([fd], [], [], 0)
    if not r:
        return None
    try:
        ch = os.read(fd, 1)
    except OSError:
        return None
    if not ch:
        return None

    if ch == b"\x1b":
        # Possibly an escape sequence (arrows, function keys). Wait briefly
        # for the rest of the sequence; if nothing follows, it was a bare ESC.
        r2, _, _ = select.select([fd], [], [], 0.005)
        if not r2:
            return "esc"
        try:
            seq = os.read(fd, 8)
        except OSError:
            return "esc"
        if seq == b"[A":
            return "up"
        if seq == b"[B":
            return "down"
        if seq == b"[C":
            return "right"
        if seq == b"[D":
            return "left"
        return "esc"

    if ch in (b"\r", b"\n"):
        return "enter"

    return ch.decode("utf-8", errors="replace")
