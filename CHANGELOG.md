# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
loosely tracks [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Picker menu** — `javalamp` (no scene) opens an interactive grid of
  live thumbnail previews. Arrow keys to navigate, enter to play, q to
  quit. The first tile is "Cycle All".
- `--cycle` flag — bypass the picker and go straight to the cycle
  behavior from v0 (still the default when stdin isn't a TTY).
- `keyboard.py` module — extracted single-key reader with proper
  arrow-key escape sequence handling. Used by both the picker and
  the scene runner.
- `Canvas.paste(other, x, y)` — composite a smaller canvas into a
  larger one at an arbitrary offset (used by the picker to assemble
  thumbnails).
- User-scene loader: drop a `.py` in `~/.config/javalamp/scenes/`
  and the scene appears in `javalamp -l` automatically — no fork required.
- `LICENSE`, `CONTRIBUTING.md`, `CHANGELOG.md`.
- GitHub Actions CI matrix (Python 3.10–3.12 × Ubuntu / macOS).
- Issue and PR templates under `.github/`.

## [0.1.0] - 2026-05-10

Initial public release.

### Scenes
- `matrix` — cascading green glyphs
- `starfield` — warp-speed 3D stars
- `donut` — the canonical a1k0n spinning torus
- `aquarium` — fish, bubbles, swaying seaweed
- `plasma` — sum-of-sines color field
- `marquee` — big-letter ASCII clock + scrolling away message
- `fireworks` — particle bursts under gravity
- `pipes` — '90s-screensaver drawing pipes
- `pollock` — drip painting in the spirit of *Number 1A, 1948*
- `twombly` — cursive scribbles + Latin annotations on cream
- `bacchus` — Twombly's overlapping loop-scribbles
- `konami` — hidden easter egg

### Themes
- `default`, `matrix`, `synthwave`, `sunset`, `mono`, `pollock`, `twombly`.
- Universal — every scene reads from the same set of color slots
  (`bg`, `fg`, `dim`, `accent`, `accent2`, `highlight`, `ramp`).

### Other
- macOS sleep guard via `caffeinate` wrapper (opt out with `--no-caffeinate`).
- Hotkeys: `q` quit · `n` next scene · `space` pause · `t` cycle theme.
- Single-letter flag aliases for everything: `-t -d -i -m -f -s -l`.
- Friendly error messages for unknown scenes (with did-you-mean
  suggestions) and bad durations.
