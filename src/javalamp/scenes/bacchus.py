"""Bacchus — Twombly's overlapping loop scribble.

Theme-driven. Loops and drips read from the active palette:
  - canvas ground   → theme.bg
  - loop colors     → theme.accent / theme.highlight / theme.fg
  - drip colors     → theme.accent / theme.highlight (the 'blood' palette
                       on the twombly theme; whatever the theme provides
                       elsewhere)

Run with `-t twombly` for red loops bleeding across parchment; any
other theme yields a different reading — synthwave: neon-magenta loops
on purple; matrix: phosphor-green loops on black.
"""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


@register
class BacchusScene(Scene):
    name = "bacchus"
    title = "Bacchus"
    description = "Overlapping loop-scribbles bleeding across the canvas."

    def setup(self) -> None:
        self.t = 0.0
        self.traversal: dict | None = None
        self.drips: list[dict] = []
        self.next_traversal = 0.4
        self.canvas_age = 0.0
        self.canvas_lifetime = self.rng.uniform(70.0, 110.0)
        self.phase = "painting"
        self.phase_until = 0.0
        self.fade_progress = 0.0
        # Loop colors: lean on accent + highlight (the saturated half of
        # most themes), with fg as a dark counterpoint.
        self._loop_pool = (self.theme.accent, self.theme.highlight, self.theme.fg)
        self._drip_pool = (self.theme.accent, self.theme.highlight)
        self._reset_canvas()

    def _reset_canvas(self) -> None:
        self.canvas.fill(" ", Style(bgcolor=self.theme.bg))

    # -- factories ----------------------------------------------------------

    def _new_traversal(self) -> dict:
        radius = max(2.5, self.rng.uniform(self.height * 0.13, self.height * 0.22))
        return dict(
            elapsed=0.0,
            duration=self.rng.uniform(10.0, 16.0),
            cy=self.rng.uniform(radius + 1, max(radius + 2, self.height - radius - 1)),
            loop_radius=radius,
            loop_freq=self.rng.uniform(1.1, 1.8),
            color=self.rng.choice(self._loop_pool),
            thickness=self.rng.choice([1, 1, 2]),
            phase=self.rng.uniform(0, math.tau),
            last_t=0.0,
        )

    def _new_drip(self, x: int, y: int, color: str) -> dict:
        length = self.rng.choices(
            [
                self.rng.uniform(2, 5),
                self.rng.uniform(5, max(6, self.height * 0.2)),
                self.rng.uniform(8, max(9, self.height * 0.45)),
            ],
            weights=[5, 3, 2],
        )[0]
        return dict(
            x=x, y=float(y), length=length,
            elapsed=0.0,
            duration=self.rng.uniform(0.6, 1.8),
            color=color,
            last_y=float(y),
        )

    # -- painting -----------------------------------------------------------

    def _mark(self, x: int, y: int, color: str, ch: str = "·",
              bold: bool = True) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        self.canvas.set(x, y, ch, Style(color=color, bgcolor=self.theme.bg, bold=bold))

    def _step_traversal(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        new_t = min(1.0, s["elapsed"] / s["duration"])
        steps = max(8, int((new_t - s["last_t"]) * 800))
        R = s["loop_radius"]
        for i in range(1, steps + 1):
            tt = s["last_t"] + (new_t - s["last_t"]) * (i / steps)
            cx = -R + (self.width + 2 * R) * tt
            loop_phase = (tt * s["duration"] * s["loop_freq"]
                          * math.tau + s["phase"])
            px = cx + R * math.sin(loop_phase)
            py = s["cy"] + R * 0.55 * math.cos(loop_phase)

            ch = self.rng.choices(
                ["o", "○", "·", "●", "*", ":", ","],
                weights=[5, 4, 5, 4, 3, 2, 2],
            )[0]
            self._mark(int(px), int(py), s["color"], ch=ch)

            if s["thickness"] >= 2:
                self._mark(int(px) + self.rng.choice([-1, 1]), int(py),
                           s["color"], ch=".")

            if math.cos(loop_phase) > 0.7 and self.rng.random() < 0.015:
                self.drips.append(self._new_drip(
                    int(px), int(py), self.rng.choice(self._drip_pool),
                ))
        s["last_t"] = new_t
        return new_t < 1.0

    def _step_drip(self, d: dict, dt: float) -> bool:
        d["elapsed"] += dt
        prog = min(1.0, d["elapsed"] / d["duration"])
        new_y = d["y"] + d["length"] * prog
        for yi in range(int(d["last_y"]) + 1, int(new_y) + 1):
            ch = self.rng.choices(["|", "│", ":", "."], weights=[5, 4, 2, 2])[0]
            self._mark(d["x"], yi, d["color"], ch=ch)
        d["last_y"] = new_y
        return prog < 1.0

    # -- main update --------------------------------------------------------

    def update(self, frame: int, dt: float) -> None:
        self.t += dt

        if self.phase == "painting":
            self.canvas_age += dt
            if self.traversal is None:
                self.next_traversal -= dt
                if self.next_traversal <= 0:
                    self.traversal = self._new_traversal()
                    self.next_traversal = self.rng.uniform(1.5, 3.5)
            else:
                if not self._step_traversal(self.traversal, dt):
                    self.traversal = None

            self.drips = [d for d in self.drips if self._step_drip(d, dt)]

            if self.canvas_age >= self.canvas_lifetime:
                self.phase = "admire"
                self.phase_until = self.t + 6.0

        elif self.phase == "admire":
            self.drips = [d for d in self.drips if self._step_drip(d, dt)]
            if self.t >= self.phase_until:
                self.phase = "fading"
                self.fade_progress = 0.0

        else:  # fading
            self.fade_progress += dt / 3.0
            n = max(20, int(self.width * self.height * 0.04))
            ground = Style(bgcolor=self.theme.bg)
            for _ in range(n):
                if self.rng.random() < self.fade_progress:
                    x = self.rng.randrange(self.width)
                    y = self.rng.randrange(self.height)
                    self.canvas.set(x, y, " ", ground)
            if self.fade_progress >= 1.4:
                self._reset_canvas()
                self.canvas_age = 0.0
                self.canvas_lifetime = self.rng.uniform(70.0, 110.0)
                self.traversal = None
                self.drips = []
                self.next_traversal = 0.4
                self.phase = "painting"
