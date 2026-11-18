"""Buddy's eyes and smile, composed from a flowing character field."""

from __future__ import annotations

import math

from rich.style import Style

from javalamp.scene import Scene, register

_GLYPHS = ".:-=+*#%@"

# Approved HTML mock:
# ?spacing=40&radius=96&mouth=250&gap=84&scale=116
_EYE_SPACING_X = 40 * 1.16 / 120
_EYE_RADIUS_X = 96 * 1.16 / 1200
_EYE_RADIUS_Y = 96 * 1.16 / 720
_MOUTH_WIDTH = 250 * 1.16 / 1200
_EYE_MOUTH_GAP = 84 * 1.16 / 720
_MOUTH_DEPTH = 58 * 1.16 / 720
_FACE_CENTER_Y = 0.49


@register
class BuddyScene(Scene):
    name = "buddy"
    title = "Buddy"
    description = "Animated eyes and a smile flowing through a field of characters."

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

    def _layout(self) -> tuple[float, float, float, float, float, float, float, float]:
        cx = self.width / 2
        eye_y = self.height * (_FACE_CENTER_Y - (_EYE_MOUTH_GAP + _MOUTH_DEPTH) / 2)
        eye_spacing = self.width * _EYE_SPACING_X
        eye_radius_x = max(1.0, self.width * _EYE_RADIUS_X)
        eye_radius_y = max(0.7, self.height * _EYE_RADIUS_Y)
        mouth_width = max(4.0, self.width * _MOUTH_WIDTH)
        mouth_top = eye_y + eye_radius_y + self.height * _EYE_MOUTH_GAP
        mouth_depth = max(1.0, self.height * _MOUTH_DEPTH)
        return (
            cx,
            eye_y,
            eye_spacing,
            eye_radius_x,
            eye_radius_y,
            mouth_width,
            mouth_top,
            mouth_depth,
        )

    @staticmethod
    def _eye_mask(
        x: int,
        y: int,
        eye_x: float,
        eye_y: float,
        radius_x: float,
        radius_y: float,
    ) -> bool:
        return ((x + 0.5 - eye_x) / radius_x) ** 2 + ((y + 0.5 - eye_y) / radius_y) ** 2 <= 1

    @staticmethod
    def _sleep_eye_mask(
        x: int,
        y: int,
        eye_x: float,
        eye_y: float,
        radius_x: float,
        radius_y: float,
    ) -> bool:
        dx = (x + 0.5 - eye_x) / radius_x
        if abs(dx) > 1:
            return False
        curve_y = eye_y + radius_y * (0.18 + 0.30 * dx * dx)
        return abs(y + 0.5 - curve_y) <= max(0.42, radius_y * 0.10)

    @staticmethod
    def _mouth_mask(
        x: int,
        y: int,
        cx: float,
        mouth_width: float,
        mouth_top: float,
        mouth_depth: float,
    ) -> bool:
        dx = x + 0.5 - cx
        half_width = mouth_width / 2
        if abs(dx) > half_width:
            return False
        normalized = dx / half_width
        curve_y = mouth_top + (1 - normalized * normalized) * mouth_depth
        return abs(y + 0.5 - curve_y) <= 0.62

    def _blink_scale(self) -> float:
        if not self.is_blinking:
            return 1.0
        progress = min(1.0, self.blink_time / self.BLINK_FOR)
        return max(0.08, abs(progress * 2 - 1))

    def _field_value(self, nx: float, ny: float, x: int, y: int, phase: float) -> float:
        wave = (
            math.sin(x * 0.19 + self.t * 1.2 + phase)
            + math.sin(y * 0.43 - self.t * 1.5 - phase)
            + math.sin((x + y * 2) * 0.11 + self.t * 0.8 + phase * 0.5)
            + math.sin(math.hypot(nx * 5, ny * 5) * 1.8 - self.t * 1.7)
        ) * 0.25
        return max(0.0, min(1.0, (wave + 1.0) * 0.5))

    def _draw_field_cell(
        self,
        x: int,
        y: int,
        nx: float,
        ny: float,
        phase: float,
        boost: float = 0.0,
    ) -> None:
        ramp = self.theme.ramp
        value = min(1.0, self._field_value(nx, ny, x, y, phase) + boost)
        glyph_index = min(len(_GLYPHS) - 1, int(value * len(_GLYPHS)))
        color_index = max(
            len(ramp) // 2,
            min(len(ramp) - 1, int(value * len(ramp))),
        )
        self.canvas.set(
            x,
            y,
            _GLYPHS[glyph_index],
            Style(
                color=ramp[color_index],
                bgcolor=self.theme.bg,
                bold=glyph_index >= len(_GLYPHS) - 2,
            ),
        )

    def _draw_features(self) -> None:
        (
            cx,
            eye_y,
            eye_spacing,
            eye_radius_x,
            eye_radius_y,
            mouth_width,
            mouth_top,
            mouth_depth,
        ) = self._layout()
        left_eye_x = cx - eye_spacing / 2
        right_eye_x = cx + eye_spacing / 2
        blink_radius_y = max(0.55, eye_radius_y * self._blink_scale())
        eye_boost = 0.34 if self.is_sparkling else 0.18

        for y in range(self.height):
            ny = (y - self.height / 2) / max(1.0, self.height / 2)
            for x in range(self.width):
                nx = (x - cx) / max(1.0, self.width / 2)
                if self.is_sleeping:
                    in_left_eye = self._sleep_eye_mask(
                        x, y, left_eye_x, eye_y, eye_radius_x, eye_radius_y
                    )
                    in_right_eye = self._sleep_eye_mask(
                        x, y, right_eye_x, eye_y, eye_radius_x, eye_radius_y
                    )
                else:
                    in_left_eye = self._eye_mask(
                        x, y, left_eye_x, eye_y, eye_radius_x, blink_radius_y
                    )
                    in_right_eye = self._eye_mask(
                        x, y, right_eye_x, eye_y, eye_radius_x, blink_radius_y
                    )
                if in_left_eye:
                    self._draw_field_cell(x, y, nx, ny, phase=-0.9, boost=eye_boost)
                elif in_right_eye:
                    self._draw_field_cell(x, y, nx, ny, phase=0.9, boost=eye_boost)
                elif self._mouth_mask(x, y, cx, mouth_width, mouth_top, mouth_depth):
                    self._draw_field_cell(x, y, nx, ny, phase=2.1, boost=0.32)

    def _draw_sleep_trail(self) -> None:
        (
            cx,
            eye_y,
            eye_spacing,
            eye_radius_x,
            eye_radius_y,
            _mouth_width,
            _mouth_top,
            _mouth_depth,
        ) = self._layout()
        phase = (self.sleep_time % 2.4) / 2.4
        for i, char in enumerate(("z", "z", "Z")):
            z_phase = (phase - i / 3 + 1) % 1
            if z_phase >= 0.8:
                continue
            progress = z_phase / 0.8
            x = round(cx + eye_spacing / 2 + eye_radius_x * (1.0 + i * 0.55))
            y = round(eye_y - eye_radius_y * (0.8 + i * 0.45 + progress * 0.45))
            self.canvas.set(
                x,
                y,
                char,
                Style(
                    color=self.theme.highlight if progress > 0.4 else self.theme.accent,
                    bgcolor=self.theme.bg,
                    bold=progress > 0.65,
                    dim=progress < 0.2,
                ),
            )

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        self._update_state(dt)
        self.canvas.clear()
        self._draw_features()
        if self.is_sleeping:
            self._draw_sleep_trail()
