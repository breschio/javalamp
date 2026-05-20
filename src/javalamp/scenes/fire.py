"""Fire effect — DOOM-style propagation up through a heat grid."""

from __future__ import annotations

from rich.style import Style

from javalamp.scene import Scene, register

_GLYPHS = " .:^*x#$@"


@register
class FireScene(Scene):
    name = "fire"
    title = "Pyre"
    description = "A roaring ASCII fire crawling up your terminal."

    def setup(self) -> None:
        self.heat = [[0] * self.width for _ in range(self.height)]
        # Hot bottom row.
        self.max_heat = len(self.theme.ramp) - 1
        for x in range(self.width):
            self.heat[self.height - 1][x] = self.max_heat

    def update(self, frame: int, dt: float) -> None:
        # Reignite the bottom row each frame, with a little flicker.
        for x in range(self.width):
            if self.rng.random() < 0.92:
                self.heat[self.height - 1][x] = self.max_heat
            else:
                self.heat[self.height - 1][x] = self.max_heat - self.rng.randint(0, 2)

        # Propagate upward: each cell takes from the cell below with random drift.
        for y in range(self.height - 2, -1, -1):
            for x in range(self.width):
                src_x = x + self.rng.randint(-1, 1)
                src_x = max(0, min(self.width - 1, src_x))
                decay = self.rng.randint(0, 2)
                self.heat[y][x] = max(0, self.heat[y + 1][src_x] - decay)

        # Render.
        self.canvas.clear()
        ramp = self.theme.ramp
        glyphs = _GLYPHS
        bg = self.theme.bg
        for y in range(self.height):
            for x in range(self.width):
                h = self.heat[y][x]
                if h <= 0:
                    continue
                gi = min(len(glyphs) - 1, max(0, h * (len(glyphs) - 1) // self.max_heat))
                ci = min(len(ramp) - 1, h)
                style = Style(color=ramp[ci], bgcolor=bg, bold=h > self.max_heat // 2)
                self.canvas.set(x, y, glyphs[gi], style)
