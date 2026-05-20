"""Big-letter ASCII clock + scrolling away message."""

from __future__ import annotations

import datetime as dt
import math

from rich.style import Style

from javalamp.scene import Scene, register

# 5x5 bitmap font for digits, colon, and a few letters used by AM/PM.
# Each entry is a list of 5 strings of width 5; '#' = on.
_FONT: dict[str, list[str]] = {
    "0": [
        " ### ",
        "#   #",
        "#   #",
        "#   #",
        " ### ",
    ],
    "1": [
        "  #  ",
        " ##  ",
        "  #  ",
        "  #  ",
        " ### ",
    ],
    "2": [
        " ### ",
        "#   #",
        "   # ",
        "  #  ",
        "#####",
    ],
    "3": [
        "#### ",
        "    #",
        "  ## ",
        "    #",
        "#### ",
    ],
    "4": [
        "#  # ",
        "#  # ",
        "#####",
        "   # ",
        "   # ",
    ],
    "5": [
        "#####",
        "#    ",
        "#### ",
        "    #",
        "#### ",
    ],
    "6": [
        " ### ",
        "#    ",
        "#### ",
        "#   #",
        " ### ",
    ],
    "7": [
        "#####",
        "    #",
        "   # ",
        "  #  ",
        " #   ",
    ],
    "8": [
        " ### ",
        "#   #",
        " ### ",
        "#   #",
        " ### ",
    ],
    "9": [
        " ### ",
        "#   #",
        " ####",
        "    #",
        " ### ",
    ],
    ":": [
        "     ",
        "  #  ",
        "     ",
        "  #  ",
        "     ",
    ],
    " ": [
        "     ",
        "     ",
        "     ",
        "     ",
        "     ",
    ],
    "A": [
        " ### ",
        "#   #",
        "#####",
        "#   #",
        "#   #",
    ],
    "P": [
        "#### ",
        "#   #",
        "#### ",
        "#    ",
        "#    ",
    ],
    "M": [
        "#   #",
        "## ##",
        "# # #",
        "#   #",
        "#   #",
    ],
}


def _render_string_to_grid(s: str) -> list[str]:
    """Render a string of supported chars into a 5-row big-letter grid."""
    rows = ["", "", "", "", ""]
    for ch in s:
        glyph = _FONT.get(ch.upper(), _FONT[" "])
        for i in range(5):
            rows[i] += glyph[i] + " "
    return rows


@register
class MarqueeScene(Scene):
    name = "marquee"
    title = "Marquee"
    description = "Big ASCII clock and a scrolling away-message."

    def setup(self) -> None:
        self.t = 0.0
        # Default away message; overridden by --message.
        self.msg = self.message or "AFK · ASCII screensaver running · be back soon"
        # Make scrolling text wrap around with separator padding.
        self.scroll_text = f"{self.msg}    ✦    "
        self.scroll_offset = 0.0

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        self.canvas.clear()

        # ---- Big clock ----
        now = dt_class().now()
        time_str = now.strftime("%I:%M")
        # strip leading zero on hour
        if time_str.startswith("0"):
            time_str = " " + time_str[1:]
        rows = _render_string_to_grid(time_str)
        gh = len(rows)
        gw = len(rows[0])
        ox = (self.width - gw) // 2
        oy = max(1, (self.height - gh) // 2 - 2)
        # Pulse the clock color slowly through the ramp.
        ramp = self.theme.ramp
        idx = int((math.sin(self.t * 0.6) + 1) * 0.5 * (len(ramp) - 1))
        big_style = Style(color=ramp[idx], bgcolor=self.theme.bg, bold=True)
        for ry, row in enumerate(rows):
            for rx, ch in enumerate(row):
                if ch == "#":
                    self.canvas.set(ox + rx, oy + ry, "█", big_style)

        # AM/PM label below
        ampm = now.strftime("%p")
        amrows = _render_string_to_grid(ampm)
        amh = len(amrows)
        amw = len(amrows[0])
        ax = (self.width - amw) // 2
        ay = oy + gh + 1
        small_style = Style(color=self.theme.accent2, bgcolor=self.theme.bg, bold=True)
        for ry, row in enumerate(amrows):
            for rx, ch in enumerate(row):
                if ch == "#":
                    self.canvas.set(ax + rx, ay + ry, "▓", small_style)

        # ---- Scrolling message ----
        msg_y = min(self.height - 2, ay + amh + 2)
        speed_chars_per_s = 14
        self.scroll_offset = (self.scroll_offset + speed_chars_per_s * dt) % len(self.scroll_text)
        offset = int(self.scroll_offset)
        line = self.scroll_text[offset:] + self.scroll_text[:offset]
        # Truncate to width.
        line = line[: self.width]
        msg_style = Style(color=self.theme.highlight, bgcolor=self.theme.bg, bold=True)
        self.canvas.text(0, msg_y, line, msg_style)

        # Underline date.
        date_str = now.strftime("%a %b %d, %Y")
        date_y = msg_y + 1
        if date_y < self.height:
            dx = max(0, (self.width - len(date_str)) // 2)
            self.canvas.text(dx, date_y, date_str,
                             Style(color=self.theme.dim, bgcolor=self.theme.bg))


# Allow tests to monkeypatch "now".
def dt_class():
    return dt.datetime
