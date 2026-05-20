"""Canvas — a 2D character/style grid that renders to a rich.Text.

Out-of-bounds writes silently no-op so scenes can paint freely without
defensive bounds-checks at every call site.
"""

from __future__ import annotations

from typing import Optional

from rich.style import Style
from rich.text import Text

# A single cell stored as (char, style-or-None). None means "use default".
Cell = tuple[str, Optional[Style]]


class Canvas:
    __slots__ = ("width", "height", "_cells", "_default_bg")

    def __init__(self, width: int, height: int, default_bg: Optional[str] = None) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self._default_bg = default_bg
        self._cells: list[list[Cell]] = self._blank_cells()

    def _blank_cells(self) -> list[list[Cell]]:
        bg = Style(bgcolor=self._default_bg) if self._default_bg else None
        return [[(" ", bg) for _ in range(self.width)] for _ in range(self.height)]

    def resize(self, width: int, height: int) -> None:
        self.width = max(1, int(width))
        self.height = max(1, int(height))
        self._cells = self._blank_cells()

    def clear(self) -> None:
        bg = Style(bgcolor=self._default_bg) if self._default_bg else None
        for row in self._cells:
            for x in range(self.width):
                row[x] = (" ", bg)

    def set(self, x: int, y: int, ch: str, style: Optional[Style] = None) -> None:
        if 0 <= x < self.width and 0 <= y < self.height and ch:
            # Take only the first char to avoid layout jitter from multi-char input.
            self._cells[y][x] = (ch[0], style)

    def fill(self, ch: str, style: Optional[Style] = None) -> None:
        for y in range(self.height):
            for x in range(self.width):
                self._cells[y][x] = (ch[0] if ch else " ", style)

    def text(self, x: int, y: int, s: str, style: Optional[Style] = None) -> None:
        if not (0 <= y < self.height):
            return
        for i, ch in enumerate(s):
            self.set(x + i, y, ch, style)

    def hline(self, x: int, y: int, length: int, ch: str = "─", style: Optional[Style] = None) -> None:
        for i in range(length):
            self.set(x + i, y, ch, style)

    def vline(self, x: int, y: int, length: int, ch: str = "│", style: Optional[Style] = None) -> None:
        for i in range(length):
            self.set(x, y + i, ch, style)

    def paste(self, other: "Canvas", x: int, y: int) -> None:
        """Composite another canvas's cells starting at (x, y).

        Cells outside this canvas's bounds are clipped silently. Useful for
        the picker: each scene renders into its own mini-canvas which we
        then paste into the picker's main canvas.
        """
        for cy in range(other.height):
            ty = y + cy
            if not (0 <= ty < self.height):
                continue
            src_row = other._cells[cy]
            dst_row = self._cells[ty]
            for cx in range(other.width):
                tx = x + cx
                if 0 <= tx < self.width:
                    dst_row[tx] = src_row[cx]

    def to_text(self) -> Text:
        """Serialize to a rich.Text with one styled span per cell."""
        text = Text(no_wrap=True, overflow="ignore")
        for y, row in enumerate(self._cells):
            # Coalesce adjacent cells with identical style for speed.
            run_chars: list[str] = []
            run_style: Optional[Style] = row[0][1] if row else None
            for ch, style in row:
                if style == run_style:
                    run_chars.append(ch)
                else:
                    text.append("".join(run_chars), style=run_style)
                    run_chars = [ch]
                    run_style = style
            if run_chars:
                text.append("".join(run_chars), style=run_style)
            if y != self.height - 1:
                text.append("\n")
        return text
