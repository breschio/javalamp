"""Fireworks — rockets launch, burst, and particles fall under gravity."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


@register
class FireworksScene(Scene):
    name = "fireworks"
    title = "Fireworks"
    description = "Rockets, bursts, and gravity-pulled particle showers."

    def setup(self) -> None:
        self.rockets: list[dict] = []
        self.particles: list[dict] = []
        self.t = 0.0
        self.next_launch = 0.5

    def _spawn_rocket(self) -> None:
        x = self.rng.uniform(self.width * 0.15, self.width * 0.85)
        target_y = self.rng.uniform(2, self.height * 0.4)
        ramp = self.theme.ramp
        color = self.rng.choice(ramp[len(ramp) // 2:])
        self.rockets.append(dict(
            x=x, y=float(self.height - 1),
            vy=-self.rng.uniform(18, 28),
            target_y=target_y,
            color=color,
            trail=[],
        ))

    def _burst(self, x: float, y: float, color: str) -> None:
        n = self.rng.randint(28, 60)
        ramp = self.theme.ramp
        # Spherical-ish distribution in 2D.
        for i in range(n):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(6, 18)
            self.particles.append(dict(
                x=x, y=y,
                vx=math.cos(angle) * speed,
                vy=math.sin(angle) * speed * 0.55,  # cell aspect
                life=self.rng.uniform(0.8, 1.6),
                age=0.0,
                color=self.rng.choice([color, ramp[-1], ramp[-2]]),
            ))

    def update(self, frame: int, dt: float) -> None:
        self.canvas.clear()
        self.t += dt
        bg = self.theme.bg

        # Background sparkle (faint stars).
        if frame % 5 == 0:
            for _ in range(self.width // 30):
                sx = self.rng.randrange(self.width)
                sy = self.rng.randrange(max(1, self.height // 2))
                self.canvas.set(sx, sy, "·",
                                Style(color=self.theme.dim, bgcolor=bg, dim=True))

        # Launch logic.
        self.next_launch -= dt
        if self.next_launch <= 0 and len(self.rockets) < 3:
            self._spawn_rocket()
            self.next_launch = self.rng.uniform(0.4, 1.4)

        # Update rockets.
        new_rockets = []
        for r in self.rockets:
            r["y"] += r["vy"] * dt
            r["vy"] += 12 * dt  # gravity slows ascent
            r["trail"].append((r["x"], r["y"]))
            if len(r["trail"]) > 8:
                r["trail"].pop(0)
            if r["y"] <= r["target_y"] or r["vy"] >= 0:
                self._burst(r["x"], r["y"], r["color"])
                continue
            # Draw trail.
            for i, (tx, ty) in enumerate(r["trail"]):
                ch = "|" if i == len(r["trail"]) - 1 else "."
                style = Style(
                    color=r["color"] if i > len(r["trail"]) - 3 else self.theme.dim,
                    bgcolor=bg,
                    bold=i == len(r["trail"]) - 1,
                )
                self.canvas.set(int(tx), int(ty), ch, style)
            new_rockets.append(r)
        self.rockets = new_rockets

        # Update particles.
        new_particles = []
        for p in self.particles:
            p["age"] += dt
            if p["age"] >= p["life"]:
                continue
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["vy"] += 14 * dt  # gravity
            p["vx"] *= 0.985
            life_t = p["age"] / p["life"]
            if life_t < 0.3:
                ch = "*"
                style = Style(color=p["color"], bgcolor=bg, bold=True)
            elif life_t < 0.6:
                ch = "+"
                style = Style(color=p["color"], bgcolor=bg)
            elif life_t < 0.85:
                ch = "."
                style = Style(color=self.theme.dim, bgcolor=bg)
            else:
                ch = "·"
                style = Style(color=self.theme.dim, bgcolor=bg, dim=True)
            self.canvas.set(int(p["x"]), int(p["y"]), ch, style)
            new_particles.append(p)
        self.particles = new_particles
