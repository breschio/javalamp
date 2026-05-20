"""Color palettes for javalamp scenes.

Each theme exposes named role colors (`bg`, `fg`, `dim`, `accent`, `accent2`,
`highlight`) and a `ramp` — an ordered list of colors going from coolest /
darkest to hottest / brightest, used by scenes that need a gradient (fire,
plasma, matrix tail, etc.).

Colors are plain strings that Rich understands ("#RRGGBB" or named).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    fg: str
    dim: str
    accent: str
    accent2: str
    highlight: str
    ramp: tuple[str, ...]


THEMES: dict[str, Theme] = {
    "default": Theme(
        name="default",
        bg="#0b0f1a",
        fg="#e6edf3",
        dim="#475569",
        accent="#60a5fa",
        accent2="#a78bfa",
        highlight="#f472b6",
        ramp=(
            "#0b0f1a", "#1e3a8a", "#3b82f6", "#60a5fa",
            "#a78bfa", "#f472b6", "#fcd34d", "#ffffff",
        ),
    ),
    "matrix": Theme(
        name="matrix",
        bg="#000000",
        fg="#39ff14",
        dim="#003b00",
        accent="#00ff41",
        accent2="#00b32a",
        highlight="#d6ffd6",
        ramp=(
            "#001a00", "#003300", "#005500", "#008f11",
            "#00b32a", "#00cc33", "#39ff14", "#d6ffd6",
        ),
    ),
    "synthwave": Theme(
        name="synthwave",
        bg="#1a0033",
        fg="#ff79c6",
        dim="#44475a",
        accent="#ff00ff",
        accent2="#00ffff",
        highlight="#fffb96",
        ramp=(
            "#1a0033", "#3d0066", "#7d00b3", "#ff00ff",
            "#ff5dcd", "#ff79c6", "#ffafd7", "#fffb96",
        ),
    ),
    "sunset": Theme(
        name="sunset",
        bg="#170029",
        fg="#ffe4b5",
        dim="#5b2a4a",
        accent="#ff6b35",
        accent2="#f7c59f",
        highlight="#ffe66d",
        ramp=(
            "#170029", "#3d0066", "#a4005c", "#ff2c5c",
            "#ff6b35", "#ff9e3b", "#ffd166", "#fffacd",
        ),
    ),
    "mono": Theme(
        name="mono",
        bg="#000000",
        fg="#ffffff",
        dim="#3a3a3a",
        accent="#bdbdbd",
        accent2="#7a7a7a",
        highlight="#ffffff",
        ramp=(
            "#000000", "#1a1a1a", "#333333", "#555555",
            "#7a7a7a", "#a0a0a0", "#cccccc", "#ffffff",
        ),
    ),
    # Engineered for the pollock scene to render close to "Number 1A, 1948":
    # cream ground, black ink, white whip-line, red/blue/yellow punctures.
    "pollock": Theme(
        name="pollock",
        bg="#e8dec7",       # canvas cream (unstretched duck)
        fg="#0a0a0a",       # ink black — primary mark
        dim="#7a6e58",      # graphite — smudges, hand prints
        accent="#a23a2e",   # vermilion (warm punctures)
        accent2="#3a5878",  # cool blue
        highlight="#fafafa",# white whip-line / brightest accent
        ramp=(
            "#e8dec7", "#d8b890", "#c9a76b", "#b07a3a",
            "#8b4a2e", "#5a2e1e", "#2a1a14", "#0a0a0a",
        ),
    ),
    # Parchment + graphite + blood reds. Used by twombly and bacchus.
    "twombly": Theme(
        name="twombly",
        bg="#ede4d3",       # parchment cream
        fg="#3a342b",       # charcoal
        dim="#7a6e58",      # softer graphite
        accent="#8b1f1f",   # blood red (drips)
        accent2="#3a5878",  # ink blue (rare)
        highlight="#a83838",# vermilion (highlights, scrawls)
        ramp=(
            "#ede4d3", "#c9b890", "#a89a78", "#8b8068",
            "#5b5444", "#a83838", "#8b1f1f", "#2a2520",
        ),
    ),
}


def get_theme(name: str) -> Theme:
    if name not in THEMES:
        raise ValueError(
            f"Unknown theme {name!r}. Available: {', '.join(sorted(THEMES))}"
        )
    return THEMES[name]


def theme_names() -> list[str]:
    return sorted(THEMES.keys())
