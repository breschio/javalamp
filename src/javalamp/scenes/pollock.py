"""Pollock — drip painting in the spirit of "Number 1A, 1948".

Theme-driven: every color is read from the active palette, so the scene
adapts to whatever theme is active. Slot mapping:

  - canvas ground       → theme.bg
  - primary line ink    → theme.fg          (~70% of line work)
  - secondary line ink  → theme.highlight   (~30%, the 'white whip')
  - color punctures     → theme.accent / accent2 / highlight (the 'tap' stroke)
  - hand prints         → theme.dim

For the closest reading of *Number 1A* run with `-t pollock` (cream
canvas, black + white, red/blue/yellow accents). Any other theme gives
a novel reading — `-t synthwave` for neon pollock on purple,
`-t matrix` for green-phosphor pollock, etc.
"""

from __future__ import annotations

from rich.style import Style

from javalamp.scene import Scene, register


_LINE_GLYPHS = "·.,'"
_DOT_GLYPHS = ".·"


def _bezier(p0, p1, p2, t):
    u = 1.0 - t
    return (
        u * u * p0[0] + 2 * u * t * p1[0] + t * t * p2[0],
        u * u * p0[1] + 2 * u * t * p1[1] + t * t * p2[1],
    )


@register
class PollockScene(Scene):
    name = "pollock"
    title = "Pollock"
    description = "Drip painting in the spirit of 'Number 1A'."

    def setup(self) -> None:
        self.t = 0.0
        self.strokes: list[dict] = []
        self.next_stroke = 0.15
        self.canvas_age = 0.0
        self.canvas_lifetime = self.rng.uniform(60.0, 90.0)
        self.phase = "painting"      # painting | admire | fading
        self.phase_until = 0.0
        self.fade_progress = 0.0
        # Cache theme-derived palette slots so the per-frame hot path
        # doesn't keep dereferencing self.theme.<x>.
        self._line_primary = self.theme.fg
        self._line_secondary = self.theme.highlight
        self._tap_pool = (self.theme.accent, self.theme.accent2, self.theme.highlight)
        self._hand_color = self.theme.dim
        self._reset_canvas()

    def _reset_canvas(self) -> None:
        self.canvas.fill(" ", Style(bgcolor=self.theme.bg))

    # -- helpers ------------------------------------------------------------

    def _edge_biased_point(self) -> tuple[float, float]:
        """Pick a point with a slight bias toward the canvas edges."""
        if self.rng.random() < 0.4:
            edge = self.rng.choice(["top", "bottom", "left", "right"])
            margin = 0.18
            if edge == "top":
                return (self.rng.uniform(0, self.width),
                        self.rng.uniform(0, self.height * margin))
            if edge == "bottom":
                return (self.rng.uniform(0, self.width),
                        self.rng.uniform(self.height * (1 - margin), self.height))
            if edge == "left":
                return (self.rng.uniform(0, self.width * margin),
                        self.rng.uniform(0, self.height))
            return (self.rng.uniform(self.width * (1 - margin), self.width),
                    self.rng.uniform(0, self.height))
        return (self.rng.uniform(0, self.width),
                self.rng.uniform(0, self.height))

    def _line_color(self) -> str:
        # 70% primary ink, 30% secondary ink — gives the duotone look on
        # palettes where fg and highlight contrast strongly with each other.
        return self._line_primary if self.rng.random() < 0.7 else self._line_secondary

    # -- stroke factories ---------------------------------------------------

    def _new_stroke(self) -> dict:
        kind = self.rng.choices(
            ["whip", "fling", "drip", "tap", "handprint"],
            weights=[8, 4, 2, 2, 1],
        )[0]
        if kind == "whip":
            return self._whip_stroke()
        if kind == "fling":
            return self._fling_stroke()
        if kind == "drip":
            return self._drip_stroke()
        if kind == "tap":
            return self._tap_stroke()
        return self._handprint_stroke()

    def _whip_stroke(self) -> dict:
        """A long, thin curved line — the dominant Pollock gesture."""
        p0 = self._edge_biased_point()
        p2 = (self.width - p0[0] + self.rng.uniform(-self.width * 0.2, self.width * 0.2),
              self.rng.uniform(0, self.height))
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
        p1 = (mx + self.rng.uniform(-self.width * 0.35, self.width * 0.35),
              my + self.rng.uniform(-self.height * 0.5, self.height * 0.5))
        return dict(
            kind="whip",
            color=self._line_color(),
            p0=p0, p1=p1, p2=p2,
            elapsed=0.0,
            duration=self.rng.uniform(0.35, 0.9),
            last_t=0.0,
        )

    def _fling_stroke(self) -> dict:
        """Medium curve with sparse single-cell spatter."""
        p0 = self._edge_biased_point()
        p2 = self._edge_biased_point()
        mx, my = (p0[0] + p2[0]) / 2, (p0[1] + p2[1]) / 2
        p1 = (mx + self.rng.uniform(-self.width * 0.25, self.width * 0.25),
              my + self.rng.uniform(-self.height * 0.4, self.height * 0.4))
        return dict(
            kind="fling",
            color=self._line_color(),
            p0=p0, p1=p1, p2=p2,
            elapsed=0.0,
            duration=self.rng.uniform(0.4, 0.9),
            last_t=0.0,
        )

    def _drip_stroke(self) -> dict:
        return dict(
            kind="drip",
            color=self._line_color(),
            x=self.rng.randint(1, self.width - 2),
            y_start=self.rng.uniform(0, self.height * 0.7),
            length=self.rng.uniform(2, max(3, self.height * 0.25)),
            elapsed=0.0,
            duration=self.rng.uniform(0.4, 1.0),
            last_y=-1.0,
        )

    def _tap_stroke(self) -> dict:
        """Tiny color accent — 1–3 dots in a tight cluster."""
        return dict(
            kind="tap",
            color=self.rng.choice(self._tap_pool),
            cx=self.rng.uniform(2, self.width - 2),
            cy=self.rng.uniform(1, self.height - 1),
            done=False,
        )

    def _handprint_stroke(self) -> dict:
        edge = self.rng.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            cx = self.rng.randint(4, max(5, self.width - 5))
            cy = self.rng.randint(0, 2)
        elif edge == "bottom":
            cx = self.rng.randint(4, max(5, self.width - 5))
            cy = self.rng.randint(max(0, self.height - 3), self.height - 1)
        elif edge == "left":
            cx = self.rng.randint(0, 2)
            cy = self.rng.randint(2, max(3, self.height - 3))
        else:
            cx = self.rng.randint(max(0, self.width - 3), self.width - 1)
            cy = self.rng.randint(2, max(3, self.height - 3))
        return dict(kind="handprint", cx=cx, cy=cy, done=False)

    # -- painting -----------------------------------------------------------

    def _mark(self, x: int, y: int, color: str, ch: str = "·",
              bold: bool = True) -> None:
        if not (0 <= x < self.width and 0 <= y < self.height):
            return
        self.canvas.set(x, y, ch, Style(color=color, bgcolor=self.theme.bg, bold=bold))

    def _step_whip(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        new_t = min(1.0, s["elapsed"] / s["duration"])
        steps = max(8, int((new_t - s["last_t"]) * 400))
        for i in range(1, steps + 1):
            tt = s["last_t"] + (new_t - s["last_t"]) * (i / steps)
            x, y = _bezier(s["p0"], s["p1"], s["p2"], tt)
            ch = self.rng.choice(_LINE_GLYPHS)
            self._mark(int(x), int(y), s["color"], ch=ch, bold=True)
        s["last_t"] = new_t
        return new_t < 1.0

    def _step_fling(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        new_t = min(1.0, s["elapsed"] / s["duration"])
        steps = max(6, int((new_t - s["last_t"]) * 300))
        for i in range(1, steps + 1):
            tt = s["last_t"] + (new_t - s["last_t"]) * (i / steps)
            x, y = _bezier(s["p0"], s["p1"], s["p2"], tt)
            ch = self.rng.choice(_LINE_GLYPHS)
            self._mark(int(x), int(y), s["color"], ch=ch, bold=True)
            if self.rng.random() < 0.04:
                self._mark(int(x) + self.rng.randint(-2, 2),
                           int(y) + self.rng.randint(-1, 1),
                           s["color"], ch=".", bold=False)
        s["last_t"] = new_t
        return new_t < 1.0

    def _step_drip(self, s: dict, dt: float) -> bool:
        s["elapsed"] += dt
        prog = min(1.0, s["elapsed"] / s["duration"])
        new_y = s["y_start"] + s["length"] * prog
        last_y = max(s["last_y"], s["y_start"] - 1)
        x = int(s["x"])
        for yi in range(int(last_y) + 1, int(new_y) + 1):
            ch = self.rng.choice([":", ".", "·"])
            self._mark(x, yi, s["color"], ch=ch)
        s["last_y"] = new_y
        return prog < 1.0

    def _step_tap(self, s: dict, _dt: float) -> bool:
        if s["done"]:
            return False
        cx, cy = int(s["cx"]), int(s["cy"])
        self._mark(cx, cy, s["color"], ch=".", bold=True)
        if self.rng.random() < 0.55:
            self._mark(cx + self.rng.randint(-1, 1),
                       cy + self.rng.randint(-1, 1),
                       s["color"], ch="·", bold=True)
        if self.rng.random() < 0.25:
            self._mark(cx + self.rng.randint(-2, 2),
                       cy + self.rng.randint(-1, 1),
                       s["color"], ch="·", bold=False)
        s["done"] = True
        return False

    def _step_handprint(self, s: dict, _dt: float) -> bool:
        if s["done"]:
            return False
        cx, cy = int(s["cx"]), int(s["cy"])
        for dy in range(-1, 3):
            for dx in range(-2, 3):
                if self.rng.random() < 0.6:
                    self._mark(cx + dx, cy + dy, self._hand_color,
                               ch=self.rng.choice(_DOT_GLYPHS), bold=False)
        s["done"] = True
        return False

    def _step_one(self, s: dict, dt: float) -> bool:
        kind = s["kind"]
        if kind == "whip":
            return self._step_whip(s, dt)
        if kind == "fling":
            return self._step_fling(s, dt)
        if kind == "drip":
            return self._step_drip(s, dt)
        if kind == "tap":
            return self._step_tap(s, dt)
        return self._step_handprint(s, dt)

    # -- main update --------------------------------------------------------

    def update(self, frame: int, dt: float) -> None:
        self.t += dt

        if self.phase == "painting":
            self.canvas_age += dt
            self.next_stroke -= dt
            while self.next_stroke <= 0:
                self.strokes.append(self._new_stroke())
                density = min(1.0, self.canvas_age / self.canvas_lifetime)
                self.next_stroke += self.rng.uniform(0.10, 0.32) + density * 0.18

            self.strokes = [s for s in self.strokes if self._step_one(s, dt)]

            if self.canvas_age >= self.canvas_lifetime:
                self.phase = "admire"
                self.phase_until = self.t + 5.0

        elif self.phase == "admire":
            if self.rng.random() < 0.015:
                self.strokes.append(self._new_stroke())
            self.strokes = [s for s in self.strokes if self._step_one(s, dt)]
            if self.t >= self.phase_until:
                self.phase = "fading"
                self.fade_progress = 0.0

        else:  # fading
            self.fade_progress += dt / 2.5
            n = max(20, int(self.width * self.height * 0.05))
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
