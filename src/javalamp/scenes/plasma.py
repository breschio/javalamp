"""Plasma — sinusoidal color field that flows across the canvas."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register

_GLYPHS = " .:-=+*#%@"


@register
class PlasmaScene(Scene):
    name = "java"
    title = "Java"
    description = "Hypnotic sine waves of color, demoscene style."

    def setup(self) -> None:
        self.t = 0.0

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        ramp = self.theme.ramp
        bg = self.theme.bg
        glyphs = _GLYPHS
        width = self.width
        height = self.height
        t = self.t

        # Precompute the sin tables we use most often.
        sin = math.sin
        for y in range(height):
            for x in range(width):
                # Normalize coords (cells are ~2:1 so x weighted lighter).
                u = x * 0.10
                v = y * 0.20
                # Classic plasma sum-of-sines.
                value = (
                    sin(u + t)
                    + sin(v + t * 1.3)
                    + sin((u + v) * 0.5 + t * 0.7)
                    + sin(math.sqrt(u * u + v * v) * 0.6 + t * 1.7)
                ) * 0.25
                # Map value [-1, 1] -> indices.
                i = (value + 1) * 0.5  # 0..1
                gi = max(0, min(len(glyphs) - 1, int(i * (len(glyphs) - 1))))
                ci = max(0, min(len(ramp) - 1, int(i * (len(ramp) - 1))))
                self.canvas.set(x, y, glyphs[gi], Style(color=ramp[ci], bgcolor=bg, bold=gi > len(glyphs) - 3))
