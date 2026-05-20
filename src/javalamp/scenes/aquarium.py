"""ASCII aquarium — fish, bubbles, swaying seaweed."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register

# Each fish is (right_facing, left_facing). One row tall keeps it readable
# at any terminal size.
_FISH = [
    ("><(((°>", "<°)))><"),
    (">-})}}*>", "<*{{{-<"),
    ("><{{{º>", "<º}}}><"),
    ("><(((>", "<)))><"),
]

_BIG_FISH = [
    ([
        r"   __",
        r"><(((°>",
    ], [
        r"     __",
        r"<°)))><",
    ]),
]


@register
class AquariumScene(Scene):
    name = "aquarium"
    title = "Aquarium"
    description = "Fish drift across, bubbles rise, seaweed sways."

    def setup(self) -> None:
        n_fish = max(4, self.width // 14)
        self.fish: list[dict] = []
        for _ in range(n_fish):
            self.fish.append(self._spawn_fish())
        self.bubbles: list[list[float]] = []
        self.t = 0.0
        # Seaweed columns: list of (x, phase, height).
        self.seaweed = []
        spacing = max(6, self.width // 12)
        for x in range(2, self.width, spacing):
            h = self.rng.randint(max(3, self.height // 4), max(4, self.height // 2))
            self.seaweed.append((x, self.rng.uniform(0, math.tau), h))

    def _spawn_fish(self, x: float | None = None) -> dict:
        sprite = self.rng.choice(_FISH)
        direction = self.rng.choice([1, -1])
        speed = self.rng.uniform(3, 9) * direction
        y = self.rng.randint(1, max(2, self.height - 3))
        if x is None:
            x = float(self.rng.randint(0, max(1, self.width - 1)))
        # Pick color from the warmer half of the ramp.
        ramp = self.theme.ramp
        color = self.rng.choice(ramp[len(ramp) // 2:])
        return dict(x=x, y=y, vx=speed, sprite=sprite, color=color, drift=self.rng.uniform(0, math.tau))

    def update(self, frame: int, dt: float) -> None:
        self.canvas.clear()
        self.t += dt
        ramp = self.theme.ramp

        # Background tint: water gradient lines (very faint dots).
        water_style = Style(color=self.theme.dim, bgcolor=self.theme.bg, dim=True)
        for y in range(self.height):
            if y % 4 == 0:
                for x in range(0, self.width, 6):
                    if self.rng.random() < 0.3:
                        self.canvas.set((x + frame // 5) % self.width, y, "·", water_style)

        # Seaweed.
        seaweed_style = Style(color=ramp[2] if len(ramp) > 2 else self.theme.accent2,
                              bgcolor=self.theme.bg)
        for x, phase, h in self.seaweed:
            for i in range(h):
                yy = self.height - 1 - i
                wobble = int(2 * math.sin(self.t * 1.5 + phase + i * 0.4))
                xx = x + wobble
                ch = "(" if (i + frame // 6) % 2 == 0 else ")"
                self.canvas.set(xx, yy, ch, seaweed_style)

        # Fish.
        for f in self.fish:
            f["x"] += f["vx"] * dt
            f["y"] += int(math.sin(self.t * 1.1 + f["drift"]) * 1.2) * 0  # subtle vertical idle
            sprite = f["sprite"][0] if f["vx"] > 0 else f["sprite"][1]
            x = int(f["x"])
            y = int(f["y"])
            if x > self.width + len(sprite) + 2:
                f["x"] = -len(sprite) - 1
                f["y"] = self.rng.randint(1, max(2, self.height - 3))
            elif x < -len(sprite) - 2:
                f["x"] = self.width + 1
                f["y"] = self.rng.randint(1, max(2, self.height - 3))
            self.canvas.text(x, y, sprite, Style(color=f["color"], bgcolor=self.theme.bg, bold=True))

        # Bubbles spawn and rise.
        if self.rng.random() < 0.4:
            self.bubbles.append([float(self.rng.randint(0, self.width - 1)),
                                 float(self.height - 1),
                                 self.rng.uniform(4, 10)])
        bubble_style = Style(color=ramp[-1], bgcolor=self.theme.bg, bold=True)
        next_bubbles = []
        for b in self.bubbles:
            b[1] -= b[2] * dt
            b[0] += math.sin(self.t * 3 + b[1] * 0.3) * 0.3
            if b[1] > 0:
                ch = "o" if b[2] > 7 else "."
                self.canvas.set(int(b[0]), int(b[1]), ch, bubble_style)
                next_bubbles.append(b)
        self.bubbles = next_bubbles

        # Sandy floor.
        sand_style = Style(color=self.theme.accent2, bgcolor=self.theme.bg)
        for x in range(self.width):
            self.canvas.set(x, self.height - 1, "~" if (x + frame // 3) % 3 else "_", sand_style)
