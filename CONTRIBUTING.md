# Contributing to javalamp

Thanks for taking the time to look! This project is built around the idea
that adding a new scene should take **less than five minutes**. If it
takes you longer, that's a bug — open an issue.

## Quick contributor checklist

1. Fork the repo and clone your fork.
2. Set up a venv and install in editable mode:
   ```sh
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[dev]"
   ```
   > **macOS + Python 3.14 gotcha**: if `pip install -e .` gives
   > `ModuleNotFoundError`, run `chflags -R nohidden .venv` once. See the
   > README's "Develop" section.
3. Add your scene (see below) or pick up an [issue](../../issues).
4. Run the tests:
   ```sh
   pytest
   ```
5. Open a PR. Small, focused changes are easier to merge.

---

## Add a scene in three steps

### 1. Try it as a user scene first (no fork needed)

You don't have to clone the repo to play. Drop a Python file in
`~/.config/javalamp/scenes/` (or `$JAVALAMP_SCENES_DIR`) and
the next `javalamp -l` will list it. Use this for personal scenes you
don't intend to upstream.

The quickest path:

```sh
javalamp new-scene lava
javalamp check-scene lava
javalamp lava
```

### 2. The minimum scene

Save this as `~/.config/javalamp/scenes/hello.py` (or as
`src/javalamp/scenes/hello.py` in a fork) and run `javalamp hello`.

```python
"""Hello — a tiny demo scene."""

from rich.style import Style
from javalamp.scene import Scene, register


@register
class HelloScene(Scene):
    name = "hello"                       # CLI key: `javalamp hello`
    title = "Hello, World"               # shown in `javalamp -l`
    description = "Bouncing greeting."

    def setup(self):
        self.x = 0
        self.dx = 1

    def update(self, frame, dt):
        self.canvas.clear()              # most scenes redraw each frame
        msg = "hello, world"
        self.x += self.dx
        if self.x + len(msg) >= self.width or self.x <= 0:
            self.dx *= -1
        self.canvas.text(
            self.x, self.height // 2, msg,
            Style(color=self.theme.fg, bgcolor=self.theme.bg, bold=True),
        )
```

That's it — `javalamp hello` works. The `Scene` base class gives you
`self.canvas` (a 2D char/style grid), `self.theme`, `self.width`,
`self.height`, and an `rng` (`random.Random` seeded for repeatability).

### 3. The full lifecycle

`Scene` is intentionally tiny. You override these:

| method | when |
|---|---|
| `setup()` | Called once after construction (and again on resize). Initialize state. |
| `update(frame, dt)` | Called every frame. Mutate state, redraw `self.canvas`. |
| `render()` | Optional. Defaults to `self.canvas.to_text()`. Override to return any `rich.console.RenderableType`. |
| `resize(w, h)` | Optional. Default rebuilds the canvas and re-runs `setup()`. |

For inspiration, the built-in scenes are deliberately small and
single-file:

- **Tiny**: `konami.py` (~50 lines, just an animated heart).
- **Stateful**: `matrix.py`, `starfield.py`, `fire.py`.
- **Persistent canvas** (no clear each frame): `pollock.py`, `pipes.py`.
- **Math-heavy**: `donut.py`, `lorenz.py` (well, when it existed —
  good template for parametric curves).
- **Theme-driven art**: `pollock.py`, `twombly.py`, `bacchus.py`.

---

## Theme integration

Read your colors from `self.theme`, not hard-coded hex strings — that
way your scene works on every theme.

| slot | typical use | example |
|---|---|---|
| `self.theme.bg` | canvas background | `Style(bgcolor=self.theme.bg)` |
| `self.theme.fg` | primary mark / text | bright text |
| `self.theme.dim` | secondary, less important | gridlines |
| `self.theme.accent` | warm accent | one-off highlights |
| `self.theme.accent2` | cool/complementary accent | pair with accent |
| `self.theme.highlight` | brightest pop color | head of a streak |
| `self.theme.ramp` | tuple of 8 colors, dark→bright | brightness gradients (fire, matrix tail) |

If your scene only makes sense with a specific palette, document it —
e.g. "looks best with `-t synthwave`" — but make sure it doesn't crash
on the others. The CI smoke test runs every scene against every theme.

---

## Code style

- Python 3.10+ syntax (`X | None`, `list[int]`, structural pattern matching).
- Format with `ruff format`. Lint with `ruff check`. (Both via `pip install -e ".[dev]"`.)
- Type hints on public APIs; loose typing inside scene bodies is fine
  (they're throwaway local state).
- Keep individual scenes < 200 lines if you can. Small, single-file
  scenes are the project aesthetic.

---

## Tests

The test suite is intentionally tiny:

- `tests/test_canvas.py` exercises the framework primitives.
- The `test_all_scenes_can_construct_and_tick` test catches obvious
  registration / import / runtime errors for *every* scene by
  constructing it and calling `update()` a few times.

If you add a built-in scene, the registry test
(`test_scene_registry_populated`) will need its expected set updated —
add your scene's `name` there.

---

## What we're looking for

**Yes please:**
- New scenes that are visually distinct from existing ones.
- Cross-platform sleep guards (Linux `systemd-inhibit`, Windows
  `SetThreadExecutionState`) — currently only macOS is wired.
- Theme additions in the spirit of the existing palettes.
- Performance wins on large terminals (3840×24+).

**Probably not:**
- Big new dependencies. The project's whole charm is `pip install`-and-go.
- Breaking the `Scene` API without a migration plan.
- Scenes that depend on external network calls or audio.

---

## Reporting issues

Open an issue with:
- Your terminal emulator + OS + Python version.
- The exact `javalamp` command you ran.
- A screenshot or asciinema recording if visual.

For "I have an idea for a scene", use the **Scene idea** issue template.

---

## License

By contributing you agree your work will be released under the [MIT
License](LICENSE).
