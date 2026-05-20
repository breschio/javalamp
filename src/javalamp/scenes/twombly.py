"""Twombly — sparse cursive scribbles and annotations on a cream ground.

Theme-driven. Slot mapping:
  - canvas ground   → theme.bg
  - line/scribble   → theme.fg / theme.dim (with theme.accent2 as accent)
  - drips           → theme.accent / theme.highlight (red-toned in twombly theme)
  - annotations     → theme.fg / theme.dim / theme.accent
  - hline           → theme.dim / theme.fg
  - smudge          → theme.bg (re-asserts ground)

Run with `-t twombly` for the parchment + graphite + blood-red look that
inspired the scene; otherwise it inherits whatever theme is active.
"""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


_ANNOTATIONS = [
    "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
    "ROMA", "ORPHEUS", "BACCHUS", "LEDA", "APOLLO", "ARCADIA",
    "OLYMPIA", "PROTEUS", "VIRGIL", "ILIUM", "ACHILLES",
    "1953", "1962", "1969", "1985",
    "5", "7", "9", "12",
    "—", "···", "??",
]


@register
class TwomblyScene(Scene):
    name = "twombly"
    title = "Twombly"
    description = "Cursive scribbles, soft drips, and Latin annotations."

    def setup(self) -> None:
        self.t = 0.0
        self.strokes: list[dict] = []
        self.next_stroke = 0.5
        self.canvas_age = 0.0
        self.canvas_lifetime = self.rng.uniform(60.0, 90.0)
        self.phase = "painting"
        self.phase_until = 0.0
        self.fade_progress = 0.0

        # Theme-derived palettes.
        # Mark colors: graphite/charcoal dominate, accents rare.
        self._mark_pool = (
            self.theme.fg,        # weight 6
            self.theme.dim,       # weight 6
            self.theme.fg,        # weight 4 (variation via repeat)
            self.theme.accent,    # weight 2
            self.theme.accent2,   # weight 2
            self.theme.highlight, # weight 2
        )
        self._mark_weights = (6, 6, 4, 2, 2, 2)
        self._drip_pool = (self.theme.accent, self.theme.highlight)
        self._line_pool = (self.theme.dim, self.theme.fg)
        self._annot_pool = (self.theme.fg, self.theme.dim, self.theme.accent)

        self._reset_canvas()

    def _reset_canvas(self) -> None:
        self.canvas.fill(" ", Style(bgcolor=self.theme.bg))

    # -- factories ----------------------------------------------------------

    def _new_stroke(self) -> dict:
        kind = self.rng.choices(
            ["scribble", "hline", "drip", "annotation", "smudge"],
            weights=[10, 3, 3, 5, 2],
        )[0]
        if kind == "scribble":
            return self._scribble_stroke()
        if kind == "hline":
            return self._hline_stroke()
        if kind == "drip":
            return self._drip_stroke()
        if kind == "annotation":
            return self._annotation_stroke()
        return self._smudge_stroke()

    def _scribble_stroke(self) -> dict:
        return dict(
            kind="scribble",
            color=self.rng.choices(self._mark_pool, weights=self._mark_weights)[0],
            cx=self.rng.uniform(self.width * 0.08, self.width * 0.92),
            cy=self.rng.uniform(self.height * 0.1, self.height * 0.9),
            radius=self.rng.uniform(2.0, 5.0),
            drift_x=self.rng.uniform(-1.2, 1.2),
            drift_y=self.rng.uniform(-0.5, 0.5),
            freq1=self.rng.uniform(5.0, 11.0),
            freq2=self.rng.uniform(3.0, 8.0),
            phase=self.rng.uniform(0, math.tau),
            elapsed=0.0,
            duration=self.rng.uniform(1.2, 2.8),
            last_t=0.0,
        )

    def _hline_stroke(self) -> dict:
        return dict(
            kind="hline",
            color=self.rng.choice(self._line_pool),
            y=self.rng.randint(int(self.height * 0.15), int(self.height * 0.85)),
            elapsed=0.0,
            duration=self.rng.uniform(1.5, 3.0),
            wave_amp=self.rng.uniform(0.4, 1.5),
            wave_freq=self.rng.uniform(0.18, 0.55),
            last_x=-1,
        )

    def _drip_stroke(self) -> dict:
        return dict(
            kind="drip",
            color=self.rng.choice(self._drip_pool),
            x=self.rng.randint(2, self.width - 3),
            y_start=self.rng.randint(0, max(1, int(self.height * 0.4))),
            length=self.rng.uniform(self.height * 0.25, self.height * 0.7),
            elapsed=0.0,
            duration=self.rng.uniform(1.0, 2.4),
            last_y=-1.0,
        )

    def _annotation_stroke(self) -> dict:
        text = self.rng.choice(_ANNOTATIONS)
        x = self.rng.randint(2, max(3, self.width - len(text) - 2))
        y = self.rng.randint(1, max(2, self.height - 2))
        return dict(
            kind="annotation",
            text=text, x=x, y=y,
            color=self.rng.choice(self._annot_pool),
            elapsed=0.0,
            duration=max(0.25, len(text) * 0.10),
            last_idx=0,
        )

    def _smudge_stroke(self) -> dict:
        return dict(
            kind="smudge",
            cx=self.rng.uniform(0, self.width),
            cy=self.rng.uniform(0, self.height),
            radius=self.rng.uniform(3, 7),
            count=self.rng.randint(20, 40),
            done=False,
        )

    # -- painting helpers ----------------------------------------------------

    def _mark(self, x: int, y: int, color: str, ch: str = "·",
              bold: bool = False) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        self.canvas.set(x, y, ch, Style(color=color, bgcolor=self.theme.bg, bold=bold))

    def _step_scribble(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        new_t = min(1.0, s["elapsed"] / s["duration"])
        steps = max(2, int((new_t - s["last_t"]) * 100))
        for i in range(1, steps + 1):
            tt = s["last_t"] + (new_t - s["last_t"]) * (i / steps)
            theta1 = tt * s["freq1"] * math.tau + s["phase"]
            theta2 = tt * s["freq2"] * math.tau + s["phase"]
            x = (s["cx"]
                 + s["radius"] * math.cos(theta1)
                 + s["drift_x"] * tt * 6)
            y = (s["cy"]
                 + s["radius"] * 0.5 * math.sin(theta2)
                 + s["drift_y"] * tt * 6)
            ch = self.rng.choices(
                ["·", "·", "·", ",", "'", ".", "o", "e", "l"],
                weights=[6, 6, 6, 3, 3, 3, 1, 1, 1],
            )[0]
            self._mark(int(x), int(y), s["color"], ch=ch)
        s["last_t"] = new_t
        return new_t < 1.0

    def _step_hline(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        prog = min(1.0, s["elapsed"] / s["duration"])
        new_x = int(self.width * prog)
        for x in range(s["last_x"] + 1, new_x + 1):
            wobble = int(math.sin(x * s["wave_freq"]) * s["wave_amp"])
            ch = self.rng.choices(
                ["─", "─", "─", "_", "~", "."],
                weights=[5, 5, 5, 2, 2, 1],
            )[0]
            self._mark(x, s["y"] + wobble, s["color"], ch=ch)
        s["last_x"] = new_x
        return prog < 1.0

    def _step_drip(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        prog = min(1.0, s["elapsed"] / s["duration"])
        new_y = s["y_start"] + s["length"] * prog
        last_y = max(s["last_y"], s["y_start"] - 1)
        x_int = int(s["x"])
        for yi in range(int(last_y) + 1, int(new_y) + 1):
            ch = self.rng.choices(["|", "|", ":", "."], weights=[5, 4, 2, 2])[0]
            self._mark(x_int, yi, s["color"], ch=ch, bold=True)
            if self.rng.random() < 0.18:
                self._mark(x_int + self.rng.choice([-1, 1]), yi,
                           s["color"], ch=".")
        s["last_y"] = new_y
        return prog < 1.0

    def _step_annotation(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        prog = min(1.0, s["elapsed"] / s["duration"])
        target_idx = int(prog * len(s["text"]))
        for i in range(s["last_idx"], min(target_idx + 1, len(s["text"]))):
            self._mark(s["x"] + i, s["y"], s["color"], ch=s["text"][i], bold=True)
        s["last_idx"] = target_idx
        return prog < 1.0

    def _step_smudge(self, s: dict, _dt: float) -> bool:
        if s["done"]:
            return False
        for _ in range(s["count"]):
            angle = self.rng.uniform(0, math.tau)
            r = self.rng.uniform(0, s["radius"])
            x = int(s["cx"] + math.cos(angle) * r)
            y = int(s["cy"] + math.sin(angle) * r * 0.55)
            if 0 <= x < self.width and 0 <= y < self.height:
                if self.rng.random() < 0.55:
                    self.canvas.set(x, y, " ", Style(bgcolor=self.theme.bg))
        s["done"] = True
        return False

    def _step_one(self, s: dict, dt: float) -> bool:
        kind = s["kind"]
        if kind == "scribble":
            return self._step_scribble(s, dt)
        if kind == "hline":
            return self._step_hline(s, dt)
        if kind == "drip":
            return self._step_drip(s, dt)
        if kind == "annotation":
            return self._step_annotation(s, dt)
        return self._step_smudge(s, dt)

    # -- main update --------------------------------------------------------

    def update(self, frame: int, dt: float) -> None:
        self.t += dt

        if self.phase == "painting":
            self.canvas_age += dt
            self.next_stroke -= dt
            while self.next_stroke <= 0:
                self.strokes.append(self._new_stroke())
                density = min(1.0, self.canvas_age / self.canvas_lifetime)
                self.next_stroke += self.rng.uniform(0.45, 1.3) + density * 0.5

            self.strokes = [s for s in self.strokes if self._step_one(s, dt)]

            if self.canvas_age >= self.canvas_lifetime:
                self.phase = "admire"
                self.phase_until = self.t + 6.0

        elif self.phase == "admire":
            if self.rng.random() < 0.012:
                self.strokes.append(self._new_stroke())
            self.strokes = [s for s in self.strokes if self._step_one(s, dt)]
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
                self.canvas_lifetime = self.rng.uniform(60.0, 90.0)
                self.strokes = []
                self.phase = "painting"
