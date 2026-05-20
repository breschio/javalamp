"""Pipes — drawing pipes of unicode box-characters meander across the screen."""

from __future__ import annotations

from rich.style import Style

from javalamp.scene import Scene, register


# Direction vectors: 0=up, 1=right, 2=down, 3=left.
_DIRS = [(0, -1), (1, 0), (0, 1), (-1, 0)]

# Pipe glyphs keyed by (incoming_dir, outgoing_dir).
# Straights: same axis. Bends: 90° turns.
_GLYPHS = {
    (0, 0): "│", (2, 2): "│",
    (1, 1): "─", (3, 3): "─",
    (1, 2): "┐", (0, 3): "┐",
    (3, 2): "┌", (0, 1): "┌",
    (1, 0): "┘", (2, 3): "┘",
    (3, 0): "└", (2, 1): "└",
}


class _Pipe:
    __slots__ = ("x", "y", "direction", "color", "life")

    def __init__(self, x: int, y: int, direction: int, color: str) -> None:
        self.x = x
        self.y = y
        self.direction = direction
        self.color = color
        self.life = 0


@register
class PipesScene(Scene):
    name = "pipes"
    title = "Pipes"
    description = "Drawing pipes meander across, '90s-screensaver style."

    def setup(self) -> None:
        self.pipes: list[_Pipe] = []
        self._spawn_initial()
        self._step_acc = 0.0
        self.step_interval = 1.0 / 22  # 22 cells/second

    def _spawn_initial(self) -> None:
        # Start with 1-3 pipes from random edges.
        for _ in range(self.rng.randint(1, 3)):
            self._spawn_one()

    def _spawn_one(self) -> None:
        ramp = self.theme.ramp
        color = self.rng.choice(ramp[3:])
        edge = self.rng.choice(["top", "bottom", "left", "right"])
        if edge == "top":
            self.pipes.append(_Pipe(self.rng.randrange(self.width), 0, 2, color))
        elif edge == "bottom":
            self.pipes.append(_Pipe(self.rng.randrange(self.width), self.height - 1, 0, color))
        elif edge == "left":
            self.pipes.append(_Pipe(0, self.rng.randrange(self.height), 1, color))
        else:
            self.pipes.append(_Pipe(self.width - 1, self.rng.randrange(self.height), 3, color))

    def step(self) -> None:
        new_pipes: list[_Pipe] = []
        for p in self.pipes:
            old_dir = p.direction
            # 14% chance to turn 90° each step.
            if self.rng.random() < 0.14:
                turn = self.rng.choice([-1, 1])
                p.direction = (p.direction + turn) % 4

            # Draw glyph at current cell using (incoming, outgoing).
            glyph = _GLYPHS.get((old_dir, p.direction)) or _GLYPHS.get((p.direction, p.direction)) or "·"
            self.canvas.set(p.x, p.y, glyph,
                            Style(color=p.color, bgcolor=self.theme.bg, bold=True))

            dx, dy = _DIRS[p.direction]
            p.x += dx
            p.y += dy
            p.life += 1

            if 0 <= p.x < self.width and 0 <= p.y < self.height and p.life < self.width * self.height:
                new_pipes.append(p)

        self.pipes = new_pipes
        # Maintain population.
        while len(self.pipes) < 2:
            self._spawn_one()
        # Occasionally retire all and start fresh for a clean look.
        if self.rng.random() < 0.001:
            self.canvas.clear()
            self.pipes = []
            self._spawn_initial()

    def update(self, frame: int, dt: float) -> None:
        # Don't clear: pipes accumulate as a drawing.
        self._step_acc += dt
        while self._step_acc >= self.step_interval:
            self._step_acc -= self.step_interval
            self.step()
