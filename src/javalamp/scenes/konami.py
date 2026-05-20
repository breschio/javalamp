"""Hidden konami easter egg — a pulsing rainbow heart."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


_HEART = [
    " ███   ███ ",
    "█████ █████",
    "███████████",
    " █████████ ",
    "  ███████  ",
    "   █████   ",
    "    ███    ",
    "     █     ",
]


@register
class KonamiScene(Scene):
    name = "konami"
    title = "↑↑↓↓←→←→BA"
    description = "(secret)"

    def setup(self) -> None:
        self.t = 0.0

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        self.canvas.clear()
        ramp = self.theme.ramp

        scale = 1.0 + 0.08 * math.sin(self.t * 4.0)
        h = len(_HEART)
        w = len(_HEART[0])
        ox = (self.width - w) // 2
        oy = max(1, (self.height - h) // 2)

        for ry, row in enumerate(_HEART):
            for rx, ch in enumerate(row):
                if ch != " ":
                    # Animate color cycling along x+y.
                    ci = int((rx + ry + self.t * 8) % len(ramp))
                    style = Style(color=ramp[ci], bgcolor=self.theme.bg, bold=True)
                    self.canvas.set(ox + rx, oy + ry, "♥", style)

        msg = "↑ ↑ ↓ ↓ ← → ← → B A"
        my = oy + h + 2
        mx = max(0, (self.width - len(msg)) // 2)
        self.canvas.text(mx, my, msg,
                         Style(color=self.theme.highlight, bgcolor=self.theme.bg, bold=True))
