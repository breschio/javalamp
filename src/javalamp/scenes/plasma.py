"""Plasma — sinusoidal color field that flows across the canvas."""

from __future__ import annotations

import math
from bisect import bisect_right
from itertools import groupby
from operator import itemgetter

from rich.segment import Segment, Segments
from rich.style import Style

from javalamp.scene import Scene, register

_GLYPHS = " .:-=+*#%@"


def _index_stops(last_index: int) -> list[float]:
    """Smallest float intensities that advance int(intensity * last_index)."""
    stops = []
    for index in range(1, last_index + 1):
        stop = index / last_index
        while int(stop * last_index) < index:
            stop = math.nextafter(stop, math.inf)
        previous = math.nextafter(stop, -math.inf)
        while int(previous * last_index) >= index:
            stop = previous
            previous = math.nextafter(stop, -math.inf)
        stops.append(stop)
    return stops


@register
class PlasmaScene(Scene):
    name = "java"
    title = "Java"
    description = "Hypnotic sine waves of color, demoscene style."

    def setup(self) -> None:
        self.t = 0.0
        self._u = [x * 0.10 for x in range(self.width)]
        self._v = [y * 0.20 for y in range(self.height)]
        phases = {}
        self._diagonal_indices = []
        self._radii = []
        for vertical in self._v:
            indices = []
            radii = []
            for horizontal in self._u:
                phase = (horizontal + vertical) * 0.5
                indices.append(phases.setdefault(phase, len(phases)))
                radii.append(math.sqrt(horizontal * horizontal + vertical * vertical) * 0.6)
            self._diagonal_indices.append(indices)
            self._radii.append(radii)
        self._diagonal_phases = list(phases)
        styles = [
            [Style(color=color, bgcolor=self.theme.bg, bold=bold) for color in self.theme.ramp]
            for bold in (False, True)
        ]
        self._palette_cells = [
            [(glyph, style) for style in styles[glyph_index > len(_GLYPHS) - 3]]
            for glyph_index, glyph in enumerate(_GLYPHS)
        ]
        last_glyph = len(_GLYPHS) - 1
        last_color = len(self.theme.ramp) - 1
        self._intensity_stops = sorted(set(_index_stops(last_glyph) + _index_stops(last_color)))
        self._intensity_cells = [self._palette_cells[0][0]] + [
            self._palette_cells[int(stop * last_glyph)][int(stop * last_color)]
            for stop in self._intensity_stops
        ]

    def update(self, frame: int, dt: float) -> None:
        self.t += dt
        t = self.t
        sin = math.sin
        horizontal_waves = [sin(horizontal + t) for horizontal in self._u]
        vertical_waves = [sin(vertical + t * 1.3) for vertical in self._v]
        diagonal_waves = [sin(phase + t * 0.7) for phase in self._diagonal_phases]
        radial_time = t * 1.7
        intensity_stops = self._intensity_stops
        intensity_cells = self._intensity_cells
        rows = self.canvas._cells
        for y, (indices, radii) in enumerate(zip(self._diagonal_indices, self._radii, strict=True)):
            vertical_wave = vertical_waves[y]
            row = rows[y]
            for x, (diagonal_index, radius) in enumerate(zip(indices, radii, strict=True)):
                value = (
                    horizontal_waves[x]
                    + vertical_wave
                    + diagonal_waves[diagonal_index]
                    + sin(radius + radial_time)
                ) * 0.25
                intensity = (value + 1) * 0.5
                row[x] = intensity_cells[bisect_right(intensity_stops, intensity)]

    def render(self) -> Segments:
        segments = []
        for row in self.canvas._cells:
            for style, cells in groupby(row, key=itemgetter(1)):
                segments.append(Segment("".join(cell[0] for cell in cells), style))
            segments.append(Segment.line())
        return Segments(segments)
