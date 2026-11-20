"""Exact plasma output checks against the original per-cell formula."""

import math
import random
from bisect import bisect_right
from dataclasses import replace
from io import StringIO
from unittest.mock import patch

import pytest
from rich.console import Console, Group
from rich.live import Live
from rich.style import Style
from rich.text import Text

from javalamp.scenes.plasma import PlasmaScene
from javalamp.theme import get_theme, theme_names


def assert_original_frame(scene):
    glyphs = " .:-=+*#%@"
    ramp = scene.theme.ramp
    for row_index, row in enumerate(scene.canvas._cells):
        for column_index, cell in enumerate(row):
            horizontal = column_index * 0.10
            vertical = row_index * 0.20
            value = (
                math.sin(horizontal + scene.t)
                + math.sin(vertical + scene.t * 1.3)
                + math.sin((horizontal + vertical) * 0.5 + scene.t * 0.7)
                + math.sin(
                    math.sqrt(horizontal * horizontal + vertical * vertical) * 0.6 + scene.t * 1.7
                )
            ) * 0.25
            intensity = (value + 1) * 0.5
            glyph_index = max(0, min(len(glyphs) - 1, int(intensity * (len(glyphs) - 1))))
            color_index = max(0, min(len(ramp) - 1, int(intensity * (len(ramp) - 1))))
            assert cell == (
                glyphs[glyph_index],
                Style(
                    color=ramp[color_index],
                    bgcolor=scene.theme.bg,
                    bold=glyph_index > len(glyphs) - 3,
                ),
            ), (column_index, row_index, scene.t)


@pytest.mark.parametrize("theme_name", theme_names())
def test_plasma_matches_original_all_themes(theme_name):
    scene = PlasmaScene(39, 13, get_theme(theme_name), random.Random(42))
    for frame, dt in enumerate((0, 1 / 12, 1 / 12, 0.37, 1000.25)):
        previous_time = scene.t
        scene.update(frame, dt)
        assert scene.t == previous_time + dt
        assert_original_frame(scene)


def test_plasma_matches_original_kiosk_and_resize():
    scene = PlasmaScene(240, 66, get_theme("mono"), random.Random(42))
    for frame in range(3):
        scene.update(frame, 1 / 12)
        assert_original_frame(scene)
    scene.resize(17, 7)
    assert scene.t == 0
    scene.update(0, 1 / 12)
    assert_original_frame(scene)
    scene.resize(240, 66)
    scene.update(0, 1 / 12)
    assert_original_frame(scene)


def test_plasma_update_reuses_geometry_and_styles():
    scene = PlasmaScene(240, 66, get_theme("mono"), random.Random(42))
    with (
        patch("javalamp.scenes.plasma.Style", side_effect=AssertionError("new Style")),
        patch("javalamp.scenes.plasma.math.sqrt", side_effect=AssertionError("new sqrt")),
        patch.object(type(scene.canvas), "set", side_effect=AssertionError("per-cell set")),
    ):
        scene.update(0, 1 / 12)
        scene.update(1, 1 / 12)
    styles = {id(style) for row in scene.canvas._cells for _, style in row}
    assert len(styles) <= 2 * len(scene.theme.ramp)
    cells = {id(cell) for row in scene.canvas._cells for cell in row}
    assert len(cells) <= 10 * len(scene.theme.ramp)


@pytest.mark.parametrize("wave_value,expected_glyph,bold", [(-1.0, " ", False), (1.0, "@", True)])
def test_plasma_index_boundaries(wave_value, expected_glyph, bold):
    scene = PlasmaScene(17, 7, get_theme("mono"), random.Random(42))
    color = scene.theme.ramp[0 if wave_value < 0 else -1]
    with patch("javalamp.scenes.plasma.math.sin", return_value=wave_value):
        scene.update(0, 1 / 12)
    expected = (expected_glyph, Style(color=color, bgcolor=scene.theme.bg, bold=bold))
    assert all(cell == expected for row in scene.canvas._cells for cell in row)


@pytest.mark.parametrize("ramp_length", [1, 3, 16])
def test_plasma_supports_different_ramp_lengths(ramp_length):
    theme = get_theme("mono")
    theme = replace(theme, ramp=(theme.ramp * 2)[:ramp_length])
    scene = PlasmaScene(39, 13, theme, random.Random(42))
    for frame in range(3):
        scene.update(frame, 1 / 12)
        assert_original_frame(scene)


@pytest.mark.parametrize("color_system", [None, "standard", "256", "truecolor"])
@pytest.mark.parametrize("dimensions", [(240, 67), (31, 12), (19, 8)])
def test_plasma_segments_match_text_terminal_output(color_system, dimensions):
    scene_width, scene_height = (240, 66) if dimensions == (240, 67) else (31, 11)
    scene = PlasmaScene(scene_width, scene_height, get_theme("mono"), random.Random(42))
    scene.update(0, 1 / 12)
    footer = Text("CPU 25% | RAM 38% | q n t")

    def capture(renderable):
        Style._add.cache_clear()
        output = StringIO()
        console = Console(
            file=output,
            force_terminal=True,
            color_system=color_system,
            width=dimensions[0],
            height=dimensions[1],
            legacy_windows=False,
        )
        with Live(Group(renderable, footer), console=console, auto_refresh=False, screen=True):
            pass
        return output.getvalue().encode("unicode_escape")

    assert capture(scene.render()) == capture(scene.canvas.to_text())


def test_plasma_render_is_an_independent_snapshot():
    scene = PlasmaScene(31, 11, get_theme("mono"), random.Random(42))
    scene.update(0, 1 / 12)
    snapshot = scene.render()
    segments = list(snapshot.segments)
    scene.update(1, 1)
    scene.resize(17, 7)
    assert snapshot.segments == segments


@pytest.mark.parametrize("ramp_length", [1, 3, 8, 16])
def test_plasma_lookup_matches_index_rounding_at_every_boundary(ramp_length):
    theme = get_theme("mono")
    scene = PlasmaScene(
        1, 1, replace(theme, ramp=(theme.ramp * 2)[:ramp_length]), random.Random(42)
    )
    intensities = [0.0, 1.0]
    for stop in scene._intensity_stops:
        intensities.extend((math.nextafter(stop, -math.inf), stop, math.nextafter(stop, math.inf)))
    intensities.extend(index / 4096 for index in range(4097))
    for intensity in intensities:
        expected = scene._palette_cells[int(intensity * 9)][int(intensity * (ramp_length - 1))]
        assert scene._intensity_cells[bisect_right(scene._intensity_stops, intensity)] == expected
