"""The famous spinning ASCII donut — a1k0n's torus, ported to colors."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register

# Luminance ramp from dim to bright.
_LUM = ".,-~:;=!*#$@"


@register
class DonutScene(Scene):
    name = "donut"
    title = "Donut"
    description = "The canonical spinning ASCII torus."

    def setup(self) -> None:
        self.A = 0.0  # x-rotation
        self.B = 0.0  # z-rotation
        # Torus parameters.
        self.R1 = 1.0
        self.R2 = 2.0
        self.K2 = 5.0
        # K1 chosen so the donut fills roughly 2/3 of the screen.
        self.K1 = self.width * self.K2 * 3 / (8 * (self.R1 + self.R2))

    def resize(self, width: int, height: int) -> None:
        super().resize(width, height)
        self.K1 = self.width * self.K2 * 3 / (8 * (self.R1 + self.R2))

    def update(self, frame: int, dt: float) -> None:
        self.canvas.clear()
        ramp = self.theme.ramp
        # z-buffer per cell.
        zbuf = [[0.0] * self.width for _ in range(self.height)]
        out = [[None] * self.width for _ in range(self.height)]

        cosA, sinA = math.cos(self.A), math.sin(self.A)
        cosB, sinB = math.cos(self.B), math.sin(self.B)

        theta = 0.0
        while theta < 2 * math.pi:
            cos_t, sin_t = math.cos(theta), math.sin(theta)
            phi = 0.0
            while phi < 2 * math.pi:
                cos_p, sin_p = math.cos(phi), math.sin(phi)
                circle_x = self.R2 + self.R1 * cos_t
                circle_y = self.R1 * sin_t

                x = (circle_x * (cosB * cos_p + sinA * sinB * sin_p)
                     - circle_y * cosA * sinB)
                y = (circle_x * (sinB * cos_p - sinA * cosB * sin_p)
                     + circle_y * cosA * cosB)
                z = self.K2 + cosA * circle_x * sin_p + circle_y * sinA
                ooz = 1.0 / z

                xp = int(self.width / 2 + self.K1 * ooz * x)
                # halve y projection so 2:1 cell aspect doesn't squash the donut
                yp = int(self.height / 2 - 0.5 * self.K1 * ooz * y)

                # luminance: dot product of normal with light vector
                L = (cos_p * cos_t * sinB - cosA * cos_t * sin_p
                     - sinA * sin_t + cosB * (cosA * sin_t - cos_t * sinA * sin_p))

                if 0 <= xp < self.width and 0 <= yp < self.height and L > 0:
                    if ooz > zbuf[yp][xp]:
                        zbuf[yp][xp] = ooz
                        li = max(0, min(int(L * 8), len(_LUM) - 1))
                        ci = max(0, min(int(L * 8), len(ramp) - 1))
                        out[yp][xp] = (_LUM[li], ramp[ci])

                phi += 0.07
            theta += 0.04

        bg = self.theme.bg
        for y in range(self.height):
            for x in range(self.width):
                cell = out[y][x]
                if cell is None:
                    continue
                ch, color = cell
                self.canvas.set(x, y, ch, Style(color=color, bgcolor=bg, bold=True))

        self.A += 0.7 * dt * 2
        self.B += 0.4 * dt * 2
