# Scene Guide

Scenes are small Python classes that redraw a terminal-sized canvas every
frame. Start as a user scene first:

```sh
javalamp new-scene lava
javalamp check-scene lava
javalamp lava
```

That creates `~/.config/javalamp/scenes/lava.py`. When it feels good, copy
it into `src/javalamp/scenes/` and import it from `src/javalamp/scenes/__init__.py`.

## Tiny Starter

```python
from rich.style import Style
from javalamp.scene import Scene, register


@register
class BlinkScene(Scene):
    name = "blink"
    title = "Blink"
    description = "A tiny blinking dot."

    def update(self, frame, dt):
        self.canvas.clear()
        if frame % 2 == 0:
            self.canvas.set(
                self.width // 2,
                self.height // 2,
                "*",
                Style(color=self.theme.highlight, bgcolor=self.theme.bg),
            )
```

## Richer Example

```python
from rich.style import Style
from javalamp.scene import Scene, register


@register
class CometsScene(Scene):
    name = "comets"
    title = "Comets"
    description = "Little streaks crossing the terminal."

    def setup(self):
        self.comets = [
            [self.rng.randrange(self.width), self.rng.randrange(self.height), self.rng.choice([-1, 1])]
            for _ in range(8)
        ]

    def update(self, frame, dt):
        self.canvas.clear()
        for comet in self.comets:
            comet[0] = (comet[0] + comet[2]) % self.width
            x, y, dx = comet
            for tail in range(5):
                color = self.theme.ramp[max(0, len(self.theme.ramp) - 1 - tail)]
                self.canvas.set(
                    x - tail * dx,
                    y,
                    "*" if tail == 0 else "-",
                    Style(color=color, bgcolor=self.theme.bg, bold=tail == 0),
                )
```

## Theme Roles

Use `self.theme` instead of hard-coded colors so every scene works with every
palette.

| role | good for |
| --- | --- |
| `bg` | canvas background |
| `fg` | main marks and readable text |
| `dim` | quiet marks, shadows, older particles |
| `accent` | warm highlights |
| `accent2` | cool/complementary highlights |
| `highlight` | brightest focal point |
| `ramp` | ordered gradient for trails, heat, depth, or brightness |

## Canvas Helpers

`self.canvas` starts at the current terminal size and silently clips
out-of-bounds writes.

| helper | use |
| --- | --- |
| `clear()` | reset the frame to the theme background |
| `set(x, y, ch, style)` | draw one character |
| `text(x, y, s, style)` | draw a string |
| `hline(...)` / `vline(...)` | draw simple rules |
| `paste(other, x, y)` | composite another canvas |

## Resize Behavior

The default `resize(width, height)` resizes the canvas and calls `setup()`
again. Put size-dependent state in `setup()` so it rebuilds cleanly after a
terminal resize. If your scene stores long-lived history, override `resize()`
carefully and keep writes clipped.

## Thumbnail Constraints

The picker renders scenes into small preview canvases. Make sure the first
few frames produce something visible at about `24x8`, avoid relying on a
single exact terminal size, and keep any labels short enough to clip
gracefully.

## PR Expectations

Public scenes should have a lowercase `name`, a friendly `title`, and a
short `description`. They should render at small, medium, and large terminal
sizes, survive every theme, avoid network calls, and stay pleasant to run in
a normal terminal.
