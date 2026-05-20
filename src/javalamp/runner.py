"""Main animation loop.

Owns the rich.live.Live instance, ticks scenes at a fixed FPS, handles
window resize via SIGWINCH, reads non-blocking single-key input from the
controlling tty for hotkeys, and orchestrates scene cycling with a wipe
transition.
"""

from __future__ import annotations

import random
import re
import shutil
import signal
import time

from rich.console import Console
from rich.live import Live
from rich.style import Style
from rich.text import Text

from javalamp.caffeinate import keep_awake
from javalamp.canvas import Canvas
from javalamp.keyboard import cbreak_stdin, read_key
from javalamp.picker import CYCLE, QUIT, Picker
from javalamp.scene import Scene, all_scenes, get_scene
from javalamp.theme import Theme, get_theme, theme_names

_DURATION_RE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*([smhd]?)\s*$", re.IGNORECASE)
_PICKER_ORDER = {
    "java": 0,
    "bacchus": 1,
    "donut": 2,
    "fireworks": 3,
    "matrix": 4,
    "pipes": 5,
    "pollock": 6,
    "starfield": 7,
    "twombly": 8,
    "aquarium": 9,
    "marquee": 10,
}


def parse_duration(value: str | None) -> float | None:
    """'5s' -> 5.0, '2m' -> 120.0, '1.5h' -> 5400.0, None -> None."""
    if value is None or value == "":
        return None
    m = _DURATION_RE.match(str(value))
    if not m:
        raise ValueError(f"Bad duration {value!r} (try '90s', '5m', '1h')")
    n, unit = float(m.group(1)), m.group(2).lower() or "s"
    return n * {"s": 1, "m": 60, "h": 3600, "d": 86400}[unit]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


class Runner:
    def __init__(
        self,
        scene_names: list[str] | None = None,
        theme_name: str | None = None,
        fps: int = 24,
        interval: float = 60.0,
        duration: float | None = None,
        message: str | None = None,
        seed: int | None = None,
        caffeinate: bool = True,
        show_picker: bool = False,
    ) -> None:
        # When theme_name is None we're in "auto" mode: each scene gets its
        # preferred_theme (or "default" if it has none). When the user
        # passes --theme explicitly, that overrides per-scene preferences
        # and applies to every scene.
        self.user_theme_name: str | None = theme_name
        self.theme: Theme = get_theme(theme_name or "default")
        self.theme_cycle = theme_names()
        self.fps = max(1, int(fps))
        self.interval = max(1.0, float(interval))
        self.duration = duration
        self.message = message
        self.rng = random.Random(seed)
        self.caffeinate = caffeinate

        # The runner always knows about every (non-easter-egg) scene so the
        # 'n' hotkey can advance through them regardless of how the session
        # started. `cycling` controls *auto-advance on the interval timer*;
        # 'n' always works.
        registered = [cls for cls in all_scenes() if cls.name != "konami"]
        self.rng.shuffle(registered)

        if scene_names:
            # Pin the requested scene first, keep the rest available for 'n'.
            target = get_scene(scene_names[0])
            others = [c for c in registered if c is not target]
            self.scene_classes = [target] + others
            # Single-scene start: don't auto-advance unless the user asks
            # (via 'n' or the cycle subcommand later).
            self.cycling = False
        else:
            self.scene_classes = list(registered)
            self.cycling = True
        self.show_picker = show_picker

        self.console = Console()
        self._stop = False
        self._next_requested = False
        self._paused = False
        self._theme_change_pending = False
        self._resize_pending = False

    # -- terminal size helpers ------------------------------------------------

    def _term_size(self) -> tuple[int, int]:
        sz = shutil.get_terminal_size((80, 24))
        # Leave 1 row for a status footer; make sure we never go below 1.
        return max(10, sz.columns), max(5, sz.lines - 1)

    # -- scene helpers --------------------------------------------------------

    def _build_scene(self, cls: type[Scene]) -> Scene:
        # Every scene uses the currently active theme — no auto-switching to
        # a scene's preferred_theme. The user's choice (via -t or the 't'
        # hotkey) sticks across scene swaps. Defaults to "default" when the
        # user hasn't picked anything.
        w, h = self._term_size()
        return cls(w, h, self.theme, self.rng, message=self.message)

    def _next_scene_class(self, idx: int) -> tuple[int, type[Scene]]:
        # Always advances when we have more than one scene available — used
        # by the 'n' hotkey and by the auto-cycle interval timer alike.
        if len(self.scene_classes) > 1:
            idx = (idx + 1) % len(self.scene_classes)
        return idx, self.scene_classes[idx]

    # -- footer ---------------------------------------------------------------

    def _footer(self, scene: Scene) -> Text:
        accent = Style(color=self.theme.accent, bold=True)
        dim = Style(color=self.theme.dim)
        bg = Style(bgcolor=self.theme.bg)
        line = Text(no_wrap=True, overflow="ellipsis")
        line.append(" ✦ javalamp ", style=accent + bg)
        line.append(f"· {scene.title} ", style=Style(color=self.theme.fg) + bg)
        line.append(f"· theme:{self.theme.name} ", style=dim + bg)
        if self._paused:
            line.append("· PAUSED ", style=Style(color=self.theme.highlight, bold=True) + bg)
        line.append("· q quit · n next · space pause · t theme", style=dim + bg)
        return line

    # -- signal handlers ------------------------------------------------------

    def _install_handlers(self) -> None:
        def on_resize(_signum, _frame):
            self._resize_pending = True

        def on_int(_signum, _frame):
            self._stop = True

        if hasattr(signal, "SIGWINCH"):
            signal.signal(signal.SIGWINCH, on_resize)
        signal.signal(signal.SIGINT, on_int)
        signal.signal(signal.SIGTERM, on_int)

    # -- transitions ----------------------------------------------------------

    def _wipe_transition(self, live: Live, from_scene: Scene, to_scene: Scene,
                        duration_s: float = 0.35) -> None:
        """Sweep a vertical wipe line left→right, clearing as it goes."""
        w, h = self._term_size()
        steps = max(8, int(duration_s * self.fps))
        wipe_style = Style(bgcolor=self.theme.accent)
        bg_style = Style(bgcolor=self.theme.bg)
        canvas = Canvas(w, h, default_bg=self.theme.bg)
        # Render the from-scene once into a "source" by capturing its current state.
        for step in range(steps + 1):
            x_edge = int((w + 2) * step / steps)
            canvas.clear()
            # Right of the edge: still show "from" (re-render from_scene)
            from_text = from_scene.render()
            # Easiest path: paint from-scene full, then overwrite columns to the left of edge.
            # We don't have direct cell access into from_text, so instead just paint:
            #   columns [0..x_edge-1] -> bg, column x_edge -> wipe_style
            # The from-scene becomes increasingly hidden as x_edge advances.
            from rich.console import Group
            mask = Canvas(w, h, default_bg=self.theme.bg)
            for y in range(h):
                for x in range(x_edge):
                    mask.set(x, y, " ", bg_style)
                if 0 <= x_edge < w:
                    mask.set(x_edge, y, " ", wipe_style)
            # Layer: from_text below, mask on top via a plain Group of two Texts
            # (rich won't composite; so we just show the mask after from to imply wipe).
            live.update(Group(from_text, mask.to_text()), refresh=True)
            time.sleep(duration_s / steps)

    # -- main loop ------------------------------------------------------------

    def run(self) -> int:
        self._install_handlers()
        target_dt = 1.0 / self.fps
        start = time.monotonic()

        with keep_awake(self.caffeinate), cbreak_stdin() as kb_fd, Live(
            console=self.console,
            refresh_per_second=self.fps,
            screen=True,
            transient=False,
        ) as live:
            # Picker phase — only when no specific scene was passed and
            # the caller asked for the menu.
            if self.show_picker:
                # Curated for the menu (the cycle uses the shuffled order
                # from __init__).
                menu_scenes = sorted(
                    [c for c in all_scenes() if c.name != "konami"],
                    key=lambda c: (_PICKER_ORDER.get(c.name, 99), c.title),
                )
                picker = Picker(
                    scene_classes=menu_scenes,
                    theme=self.theme,
                    rng=self.rng,
                )
                result = picker.run(live, kb_fd)
                self.theme = picker.theme
                self.user_theme_name = picker.theme.name
                if result is QUIT:
                    return 0
                if result is CYCLE:
                    self.cycling = True
                    # self.scene_classes already holds the shuffled list.
                else:
                    # A specific Scene class was returned. Pin it first but
                    # keep all other scenes available so 'n' still advances.
                    target = result
                    others = [c for c in self.scene_classes if c is not target]
                    self.scene_classes = [target] + others
                    self.cycling = False

            idx = 0
            scene = self._build_scene(self.scene_classes[idx])
            scene_started = time.monotonic()
            frame = 0

            while not self._stop:
                tick_start = time.monotonic()

                # Handle resize.
                if self._resize_pending:
                    self._resize_pending = False
                    w, h = self._term_size()
                    scene.resize(w, h)

                # Read one key per tick (drain a few while we're at it).
                for _ in range(8):
                    key = read_key(kb_fd)
                    if key is None:
                        break
                    if key in ("q", "Q", "\x03"):  # q or Ctrl-C
                        self._stop = True
                    elif key in ("n", "N"):
                        self._next_requested = True
                    elif key == " ":
                        self._paused = not self._paused
                    elif key in ("t", "T"):
                        self._theme_change_pending = True

                # Theme change.
                if self._theme_change_pending:
                    self._theme_change_pending = False
                    cur = self.theme_cycle.index(self.theme.name)
                    new_name = self.theme_cycle[(cur + 1) % len(self.theme_cycle)]
                    # Pressing 't' is an explicit user choice — pin it so
                    # subsequent scene swaps don't snap back to per-scene
                    # preferred themes.
                    self.user_theme_name = new_name
                    self.theme = get_theme(new_name)
                    # Rebuild current scene to pick up new theme.
                    scene = self.scene_classes[idx](
                        scene.width, scene.height, self.theme, self.rng,
                        message=self.message,
                    )

                # Update + render.
                if not self._paused:
                    scene.update(frame, target_dt)
                    frame += 1

                from rich.console import Group
                live.update(Group(scene.render(), self._footer(scene)))

                # Should we cycle?
                now = time.monotonic()
                cycle_due = self.cycling and (now - scene_started) >= self.interval
                if self._next_requested or cycle_due:
                    self._next_requested = False
                    idx, next_cls = self._next_scene_class(idx)
                    next_scene = self._build_scene(next_cls)
                    self._wipe_transition(live, scene, next_scene)
                    scene = next_scene
                    scene_started = time.monotonic()
                    frame = 0

                # Duration cap.
                if self.duration is not None and (now - start) >= self.duration:
                    self._stop = True
                    break

                # FPS clock.
                elapsed = time.monotonic() - tick_start
                sleep_for = target_dt - elapsed
                if sleep_for > 0:
                    time.sleep(sleep_for)

        return 0
