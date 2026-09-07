"""A centered ASCII face that blinks, sparkles, sleeps, and wakes."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register


@register
class BuddyScene(Scene):
    name = "buddy"
    title = "Buddy"
    description = "A friendly face that blinks, sparkles, and dozes off."

    SLEEP_AFTER = 45.0
    SLEEP_FOR = 10.0
    SPARKLE_FOR = 3.0
    BLINK_FOR = 0.15

    def setup(self) -> None:
        self.t = 0.0
        self.awake_time = 0.0
        self.sleep_time = 0.0
        self.is_sleeping = False
        self.is_blinking = False
        self.is_sparkling = False
        self.next_blink = self.rng.uniform(3.0, 5.0)
        self.next_sparkle = self.rng.uniform(8.0, 14.0)
        self.blink_time = 0.0
        self.sparkle_time = 0.0

    def _scale(self) -> tuple[int, int]:
        # Buddy's browser canvas uses square cells. Typical terminal cells are
        # roughly four times narrower and twice as short, so preserve the
        # source artwork's proportions by expanding its coordinate grid.
        x_scale = 4 if self.width >= 48 else 2 if self.width >= 32 else 1
        y_scale = 2 if self.height >= 12 else 1
        return x_scale, y_scale

    def _place(
        self,
        cx: int,
        cy: int,
        x: float,
        y: float,
        char: str,
        style: Style,
        x_scale: int,
        y_scale: int,
    ) -> None:
        self.canvas.set(
            cx + round(x * x_scale),
            cy + round(y * y_scale),
            char,
            style,
        )

    def _wake(self) -> None:
        self.awake_time = 0.0
        self.sleep_time = 0.0
        self.is_sleeping = False
        self.is_blinking = False
        self.is_sparkling = False
        self.next_blink = self.rng.uniform(3.0, 5.0)
        self.next_sparkle = self.rng.uniform(8.0, 14.0)

    def _update_state(self, dt: float) -> None:
        if self.is_sleeping:
            self.sleep_time += dt
            if self.sleep_time >= self.SLEEP_FOR:
                self._wake()
            return

        self.awake_time += dt
        if self.awake_time >= self.SLEEP_AFTER:
            self.is_sleeping = True
            self.is_blinking = False
            self.is_sparkling = False
            self.sleep_time = 0.0
            return

        if self.is_blinking:
            self.blink_time += dt
            if self.blink_time >= self.BLINK_FOR:
                self.is_blinking = False
                self.next_blink = self.rng.uniform(3.0, 5.0)
        else:
            self.next_blink -= dt
            if self.next_blink <= 0:
                self.is_blinking = True
                self.blink_time = 0.0

        if self.is_sparkling:
            self.sparkle_time += dt
            if self.sparkle_time >= self.SPARKLE_FOR:
                self.is_sparkling = False
                self.next_sparkle = self.rng.uniform(12.0, 20.0)
        else:
            self.next_sparkle -= dt
            if self.next_sparkle <= 0:
                self.is_sparkling = True
                self.sparkle_time = 0.0

    def _draw_sleep(
        self,
        cx: int,
        cy: int,
        style: Style,
        x_scale: int,
        y_scale: int,
    ) -> None:
        self._place(cx, cy, -4, -1, "^", style, x_scale, y_scale)
        self._place(cx, cy, 4, -1, "^", style, x_scale, y_scale)

        phase = (self.sleep_time % 2.4) / 2.4
        for i, char in enumerate(("z", "z", "Z")):
            z_phase = (phase - i / 3 + 1) % 1
            if z_phase >= 0.8:
                continue
            progress = z_phase / 0.8
            fade = math.sin(progress * math.pi)
            z_style = Style(
                color=self.theme.fg if fade > 0.55 else self.theme.dim,
                bgcolor=self.theme.bg,
                bold=fade > 0.8,
                dim=fade < 0.35,
            )
            self._place(
                cx,
                cy,
                7 + i * 1.2,
                -3 - i * 1.5 - progress * 2,
                char,
                z_style,
                x_scale,
                y_scale,
            )

    def _draw_awake(
        self,
        cx: int,
        cy: int,
        style: Style,
        x_scale: int,
        y_scale: int,
    ) -> None:
        if self.is_blinking:
            return

        eye = "(-)" if self.is_sparkling else "(●)"
        for offset, char in enumerate(eye):
            self._place(cx, cy, -5 + offset, -1, char, style, x_scale, y_scale)
            self._place(cx, cy, 3 + offset, -1, char, style, x_scale, y_scale)

        if self.is_sparkling:
            pulse = 0.5 + math.sin(self.t * 2.0) * 0.2
            blush_style = Style(
                color=self.theme.highlight if pulse > 0.5 else self.theme.accent,
                bgcolor=self.theme.bg,
                bold=pulse > 0.6,
                dim=pulse < 0.4,
            )
            self._place(cx, cy, -7, 0, "*", blush_style, x_scale, y_scale)
            self._place(cx, cy, 7, 0, "*", blush_style, x_scale, y_scale)

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        self._update_state(dt)
        self.canvas.clear()

        x_scale, y_scale = self._scale()
        cx = self.width // 2 - (2 if x_scale == 4 else 0)
        cy = self.height // 2
        face_style = Style(color=self.theme.fg, bgcolor=self.theme.bg, bold=True)

        if self.is_sleeping:
            self._draw_sleep(cx, cy, face_style, x_scale, y_scale)
        else:
            self._draw_awake(cx, cy, face_style, x_scale, y_scale)

        for offset, char in enumerate(r"\___/"):
            self._place(cx, cy, -2 + offset, 2, char, face_style, x_scale, y_scale)
