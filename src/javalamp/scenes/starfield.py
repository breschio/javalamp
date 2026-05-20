"""Warp-speed starfield — three depth layers zooming past."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


@register
class StarfieldScene(Scene):
    name = "starfield"
    title = "Warp Starfield"
    description = "3D stars accelerating past the camera."

    def setup(self) -> None:
        n = max(80, (self.width * self.height) // 16)
        self.stars: list[list[float]] = []
        for _ in range(n):
            self.stars.append(self._spawn_star())
        # Time accumulator for warp pulse.
        self.t = 0.0

    def _spawn_star(self) -> list[float]:
        # Stored as [x, y, z] in normalized coords centered at origin.
        # x,y in [-1,1], z in (0,1] (smaller z = closer to camera).
        return [
            self.rng.uniform(-1.0, 1.0),
            self.rng.uniform(-1.0, 1.0),
            self.rng.uniform(0.05, 1.0),
        ]

    def update(self, frame: int, dt: float) -> None:
        self.canvas.clear()
        self.t += dt
        cx = self.width / 2
        cy = self.height / 2
        # Pulse speed so it feels organic.
        speed = 0.55 + 0.45 * (math.sin(self.t * 0.7) * 0.5 + 0.5)
        ramp = self.theme.ramp
        bg = Style(bgcolor=self.theme.bg)

        for s in self.stars:
            s[2] -= speed * dt
            if s[2] <= 0.02:
                # Respawn far away with new x/y.
                s[0] = self.rng.uniform(-1.0, 1.0)
                s[1] = self.rng.uniform(-1.0, 1.0)
                s[2] = 1.0
                continue
            # Project to screen.
            k = 0.5 / s[2]
            sx = int(cx + s[0] * cx * k)
            sy = int(cy + s[1] * cy * k * 0.55)  # cells are ~2x taller than wide
            if not (0 <= sx < self.width and 0 <= sy < self.height):
                continue
            # Closer = brighter glyph + brighter color.
            depth = 1.0 - s[2]
            if depth > 0.85:
                ch, style = "✦", Style(color=ramp[-1], bgcolor=self.theme.bg, bold=True)
            elif depth > 0.65:
                ch, style = "*", Style(color=ramp[-2], bgcolor=self.theme.bg, bold=True)
            elif depth > 0.4:
                ch, style = "+", Style(color=ramp[-3], bgcolor=self.theme.bg)
            elif depth > 0.2:
                ch, style = ".", Style(color=ramp[-5] if len(ramp) > 5 else self.theme.fg, bgcolor=self.theme.bg)
            else:
                ch, style = "·", Style(color=self.theme.dim, bgcolor=self.theme.bg, dim=True)

            # Draw a short streak behind the star to imply motion.
            if depth > 0.55:
                # Direction from center.
                dx = s[0]
                dy = s[1] * 0.55
                length = max(0.0, math.hypot(dx, dy))
                if length > 0.01:
                    streak_len = int(2 + depth * 4)
                    for i in range(1, streak_len + 1):
                        bx = int(sx - (dx / length) * i)
                        by = int(sy - (dy / length) * i)
                        self.canvas.set(bx, by, "·", Style(color=ramp[max(0, len(ramp) - 5)], bgcolor=self.theme.bg, dim=True))
            self.canvas.set(sx, sy, ch, style)
