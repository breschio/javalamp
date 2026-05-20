"""Picker — interactive scene-selection menu with live thumbnail previews.

Layout: a responsive grid of mini-canvases (one per scene) plus a special
"Cycle All" tile. Each tile is a fully-running scene at thumbnail size,
ticked every frame. Arrow keys move focus, Enter chooses, q/Esc quits.
"""

from __future__ import annotations

import math
import random
import shutil
import time

from rich.live import Live
from rich.style import Style

from javalamp.canvas import Canvas
from javalamp.keyboard import read_key
from javalamp.scene import Scene
from javalamp.theme import Theme, get_theme, theme_names

# Result sentinels returned by Picker.run()
QUIT = object()
CYCLE = object()

_WORDMARK = [
    "     _                  _                       ",
    "    (_)                | |                      ",
    "     _  __ ___   ____ _| | __ _ _ __ ___  _ __  ",
    "    | |/ _` \\ \\ / / _` | |/ _` | '_ ` _ \\| '_ \\ ",
    "    | | (_| |\\ V / (_| | | (_| | | | | | | |_) |",
    "    | |\\__,_| \\_/ \\__,_|_|\\__,_|_| |_| |_| .__/ ",
    "   _/ |                                  | |    ",
    "  |__/                                   |_|    ",
]
_SMALL_WORDMARK = [
    "javalamp",
]
_TAGLINE = "A glowing terminal screensaver that keeps your Mac awake"


class _Tile:
    """One picker tile — wraps a Scene at thumbnail size, plus its label."""

    __slots__ = ("name", "title", "description", "scene_cls", "scene", "is_special")

    def __init__(self, scene_cls: type[Scene] | None, theme: Theme,
                 rng: random.Random, content_w: int, content_h: int,
                 is_special: bool = False) -> None:
        self.is_special = is_special
        self.scene_cls = scene_cls
        if is_special:
            self.name = "cycle"
            self.title = "Cycle All"
            self.description = "Play every scene in sequence (~60s each)."
            self.scene = None
        else:
            assert scene_cls is not None
            self.name = scene_cls.name
            self.title = scene_cls.title
            self.description = scene_cls.description
            try:
                # Each tile gets its own RNG stream so previews don't all
                # animate in lockstep.
                tile_rng = random.Random(rng.random())
                self.scene = scene_cls(content_w, content_h, theme, tile_rng)
            except Exception:
                self.scene = None

    def update(self, frame: int, dt: float) -> None:
        if self.scene is not None:
            try:
                self.scene.update(frame, dt)
            except Exception:
                # One bad scene shouldn't break the picker.
                self.scene = None


class Picker:
    """Renders the menu and handles input until selection or quit."""

    HEADER_LINES = 10   # wordmark + tagline + blank
    FOOTER_LINES = 4   # blank + selected-description + blank + hint
    TILE_GAP_X = 2
    TILE_GAP_Y = 1
    # Preferred (target) tile dimensions — used on wide terminals.
    PREFERRED_TILE_W = 44
    PREFERRED_TILE_H = 12  # 10 inner rows + top/bottom border
    # Minimum tile dimensions — used as fallback on tight terminals so the
    # picker still fits something usable.
    MIN_TILE_W = 22
    MIN_TILE_H = 5

    def __init__(self, scene_classes: list[type[Scene]], theme: Theme,
                 rng: random.Random, fps: int = 12) -> None:
        self.scene_classes = scene_classes
        self.theme = theme
        self.rng = rng
        self.fps = fps
        self.theme_cycle = theme_names()
        self.focused = 0
        self.frame = 0
        self.tiles: list[_Tile] = []
        self.canvas: Canvas | None = None
        self._term_size_cache: tuple[int, int] | None = None
        self.cols = 1
        self.rows = 1
        self.tile_w = self.PREFERRED_TILE_W
        self.tile_h = self.PREFERRED_TILE_H

    # -- layout -------------------------------------------------------------

    def _term_size(self) -> tuple[int, int]:
        sz = shutil.get_terminal_size((80, 24))
        return max(60, sz.columns), max(20, sz.lines - 1)

    def _compute_layout(self) -> None:
        w, h = self._term_size()
        n = len(self.scene_classes) + 1  # +1 for the Cycle tile
        self.HEADER_LINES = self._header_height(w)

        # Tile width: prefer the larger size, but fall back to the compact
        # size if that's the only way to keep at least 2 columns. Single-
        # column layouts are claustrophobic.
        tile_w = self.PREFERRED_TILE_W
        if (w - 2) // (tile_w + self.TILE_GAP_X) < 2:
            tile_w = self.MIN_TILE_W
        max_cols = max(1, (w - 2) // (tile_w + self.TILE_GAP_X))
        cols = min(max_cols, n)
        rows = math.ceil(n / cols)

        # Tile height: prefer the larger size, shrink if the grid would
        # overflow the available height. Floor at MIN_TILE_H.
        tile_h = self.PREFERRED_TILE_H
        avail_h = h - self.HEADER_LINES - self.FOOTER_LINES
        needed_h = rows * tile_h + (rows - 1) * self.TILE_GAP_Y
        if needed_h > avail_h:
            tile_h = max(
                self.MIN_TILE_H,
                (avail_h - (rows - 1) * self.TILE_GAP_Y) // rows,
            )

        self.cols = cols
        self.rows = rows
        self.tile_w = tile_w
        self.tile_h = tile_h
        self._term_size_cache = (w, h)

        # (Re)build tiles at the computed inner size.
        content_w = tile_w - 2  # minus left/right border
        content_h = tile_h - 2  # minus top/bottom border
        tiles: list[_Tile] = [
            _Tile(None, self.theme, self.rng, content_w, content_h, is_special=True),
        ]
        for cls in self.scene_classes:
            tiles.append(_Tile(cls, self.theme, self.rng, content_w, content_h))
        self.tiles = tiles
        self.canvas = Canvas(w, h, default_bg=self.theme.bg)
        # Clamp focus index to valid range.
        if self.focused >= len(tiles):
            self.focused = len(tiles) - 1

    def _maybe_relayout(self) -> None:
        if self._term_size_cache != self._term_size():
            self._compute_layout()

    def _cycle_theme(self) -> None:
        cur = self.theme_cycle.index(self.theme.name)
        self.theme = get_theme(self.theme_cycle[(cur + 1) % len(self.theme_cycle)])
        self._compute_layout()

    # -- update + render ----------------------------------------------------

    def update(self, dt: float) -> None:
        self._maybe_relayout()
        for tile in self.tiles:
            tile.update(self.frame, dt)
        self.frame += 1

    def _render_tile(self, tile: _Tile, ox: int, oy: int, focused: bool) -> None:
        canvas = self.canvas
        w, h = self.tile_w, self.tile_h

        border_color = self.theme.accent if focused else self.theme.dim
        border_style = Style(color=border_color, bgcolor=self.theme.bg, bold=focused)

        # Top + bottom borders.
        canvas.set(ox, oy, "┌", border_style)
        canvas.set(ox + w - 1, oy, "┐", border_style)
        canvas.set(ox, oy + h - 1, "└", border_style)
        canvas.set(ox + w - 1, oy + h - 1, "┘", border_style)
        for i in range(1, w - 1):
            canvas.set(ox + i, oy, "─", border_style)
            canvas.set(ox + i, oy + h - 1, "─", border_style)
        for j in range(1, h - 1):
            canvas.set(ox, oy + j, "│", border_style)
            canvas.set(ox + w - 1, oy + j, "│", border_style)

        # Title in the top border (truncated).
        title = tile.title
        marker = "▶ " if focused else "  "
        title_text = (marker + title)[: w - 4]
        title_color = self.theme.fg if focused else self.theme.dim
        canvas.text(ox + 2, oy, title_text,
                    Style(color=title_color, bgcolor=self.theme.bg, bold=focused))

        # Content area.
        cx, cy = ox + 1, oy + 1
        cw, ch = w - 2, h - 2
        if tile.is_special:
            self._render_cycle_tile(cx, cy, cw, ch)
        elif tile.scene is not None:
            canvas.paste(tile.scene.canvas, cx, cy)
        else:
            # Broken scene fallback.
            label = "[unavailable]"
            canvas.text(cx + max(0, (cw - len(label)) // 2),
                        cy + ch // 2, label,
                        Style(color=self.theme.dim, bgcolor=self.theme.bg))

    def _render_cycle_tile(self, ox: int, oy: int, w: int, h: int) -> None:
        """A small swirling-sparkle pattern + 'CYCLE' label."""
        canvas = self.canvas
        cx_, cy_ = ox + w / 2, oy + h / 2
        sparkles = "✦*·★+"
        # Animated sparkles orbiting the center.
        for i in range(min(20, w * h // 3)):
            angle = (self.frame * 0.05 + i * 0.31) % math.tau
            r = (i % 4) + 0.5
            x = int(cx_ + math.cos(angle) * r * 1.6)
            y = int(cy_ + math.sin(angle) * r * 0.9)
            if ox <= x < ox + w and oy <= y < oy + h:
                canvas.set(x, y, sparkles[i % len(sparkles)],
                           Style(color=self.theme.highlight,
                                 bgcolor=self.theme.bg, bold=True))
        label = "CYCLE"
        if w >= len(label):
            canvas.text(int(cx_) - len(label) // 2, int(cy_), label,
                        Style(color=self.theme.accent, bgcolor=self.theme.bg, bold=True))

    def _header_height(self, width: int) -> int:
        if width >= max(len(line) for line in _WORDMARK):
            return len(_WORDMARK) + 3
        return len(_SMALL_WORDMARK) + 3

    def _render_header(self) -> None:
        canvas = self.canvas
        assert canvas is not None

        art = _WORDMARK if canvas.width >= max(len(line) for line in _WORDMARK) else _SMALL_WORDMARK
        use_shadow = False
        foreground_cells = set()
        for y, line in enumerate(art):
            x0 = max(0, (canvas.width - len(line)) // 2)
            for x, ch in enumerate(line):
                if ch != " ":
                    foreground_cells.add((x0 + x, y))

        palette = (
            self.theme.highlight,
            self.theme.accent,
            self.theme.accent2,
            self.theme.fg,
            self.theme.accent,
        )

        for y, line in enumerate(art):
            x0 = max(0, (canvas.width - len(line)) // 2)
            if use_shadow:
                for x, ch in enumerate(line):
                    if ch == " ":
                        continue
                    sx = x0 + x + 1
                    sy = y + 1
                    if sy <= len(art) and 0 <= sx < canvas.width and (sx, sy) not in foreground_cells:
                        canvas.set(
                            sx,
                            sy,
                            ch,
                            Style(color=self.theme.dim, bgcolor=self.theme.bg),
                        )
            for x, ch in enumerate(line):
                if ch == " ":
                    continue
                color = palette[(x // 3 + y + self.frame // 4) % len(palette)]
                canvas.set(
                    x0 + x,
                    y,
                    ch,
                    Style(color=color, bgcolor=self.theme.bg, bold=True),
                )

        tagline = _TAGLINE
        if len(tagline) > canvas.width - 4:
            tagline = "Glowing terminal screensaver + Mac sleep guard"
        canvas.text(
            max(0, (canvas.width - len(tagline)) // 2),
            len(art) + 1,
            tagline,
            Style(color=self.theme.fg, bgcolor=self.theme.bg, bold=True),
        )

    def render(self):
        canvas = self.canvas
        canvas.fill(" ", Style(bgcolor=self.theme.bg))

        self._render_header()

        # Center the grid horizontally.
        grid_w = self.cols * self.tile_w + (self.cols - 1) * self.TILE_GAP_X
        grid_x = max(0, (canvas.width - grid_w) // 2)
        grid_y = self.HEADER_LINES

        for i, tile in enumerate(self.tiles):
            row, col = divmod(i, self.cols)
            ox = grid_x + col * (self.tile_w + self.TILE_GAP_X)
            oy = grid_y + row * (self.tile_h + self.TILE_GAP_Y)
            # Skip if this tile would render off the bottom of the screen.
            if oy + self.tile_h > canvas.height - self.FOOTER_LINES + 1:
                continue
            self._render_tile(tile, ox, oy, focused=(i == self.focused))

        # Footer: focused description + hotkey hint.
        focused = self.tiles[self.focused]
        desc = f"▶ {focused.title} · {focused.description}"
        desc = desc[: canvas.width - 4]
        canvas.text(max(0, (canvas.width - len(desc)) // 2), canvas.height - 3, desc,
                    Style(color=self.theme.fg, bgcolor=self.theme.bg, bold=True))

        hint = "←→↑↓ navigate · enter to play · t theme · q to quit · / for list"
        if len(hint) > canvas.width - 4:
            hint = "← → ↑ ↓ navigate · enter · t theme · q quit"
        canvas.text(max(0, (canvas.width - len(hint)) // 2),
                    canvas.height - 1, hint,
                    Style(color=self.theme.dim, bgcolor=self.theme.bg))

        return canvas.to_text()

    # -- input --------------------------------------------------------------

    def _move(self, key: str) -> None:
        n = len(self.tiles)
        if key == "left":
            if self.focused % self.cols > 0:
                self.focused -= 1
            else:
                # Wrap to right end of same row.
                row_start = (self.focused // self.cols) * self.cols
                self.focused = min(row_start + self.cols - 1, n - 1)
        elif key == "right":
            row = self.focused // self.cols
            row_end = min((row + 1) * self.cols - 1, n - 1)
            if self.focused < row_end:
                self.focused += 1
            else:
                self.focused = row * self.cols
        elif key == "up":
            if self.focused >= self.cols:
                self.focused -= self.cols
            else:
                # Wrap to bottom of same column.
                col = self.focused
                last_row = (n - 1) // self.cols
                target = last_row * self.cols + col
                if target >= n:
                    target -= self.cols
                self.focused = target
        elif key == "down":
            target = self.focused + self.cols
            if target < n:
                self.focused = target
            else:
                self.focused = self.focused % self.cols

    def _handle(self, key: str):
        """Returns: None to continue, QUIT, CYCLE, or a Scene class."""
        if key in ("q", "Q", "\x03", "esc"):
            return QUIT
        if key in ("left", "right", "up", "down"):
            self._move(key)
            return None
        if key in ("t", "T"):
            self._cycle_theme()
            return None
        if key == "enter":
            tile = self.tiles[self.focused]
            return CYCLE if tile.is_special else tile.scene_cls
        return None

    # -- main loop ----------------------------------------------------------

    def run(self, live: Live, kb_fd: int | None):
        """Drive the picker until selection or quit. Returns:
        - QUIT if the user quit
        - CYCLE if the user picked the cycle tile (or stdin isn't a TTY)
        - a Scene subclass if the user picked a specific scene
        """
        # Without a TTY we can't read keys, so the picker would hang.
        # Fall through to cycle mode in that case.
        if kb_fd is None:
            return CYCLE

        self._compute_layout()
        target_dt = 1.0 / self.fps
        last = time.monotonic()

        while True:
            tick_start = time.monotonic()
            dt = tick_start - last
            last = tick_start

            for _ in range(8):
                key = read_key(kb_fd)
                if key is None:
                    break
                result = self._handle(key)
                if result is not None:
                    return result

            self.update(dt)
            live.update(self.render())

            elapsed = time.monotonic() - tick_start
            sleep_for = target_dt - elapsed
            if sleep_for > 0:
                time.sleep(sleep_for)
