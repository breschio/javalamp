"""Sanity tests for Canvas, Scene registry, and the runner's duration parser."""

from __future__ import annotations

import pytest
from rich.style import Style

from javalamp.canvas import Canvas
from javalamp.runner import parse_duration


def test_canvas_dimensions_clamped_to_one():
    c = Canvas(0, 0)
    assert c.width == 1 and c.height == 1


def test_canvas_set_in_bounds():
    c = Canvas(5, 3)
    c.set(2, 1, "x", Style(color="red"))
    text = c.to_text()
    rendered = text.plain.split("\n")
    assert rendered[1][2] == "x"


def test_canvas_set_out_of_bounds_is_silent():
    c = Canvas(4, 2)
    c.set(99, 99, "z")
    c.set(-1, -1, "z")
    c.set(0, 5, "z")
    # No exception, no z anywhere.
    assert "z" not in c.to_text().plain


def test_canvas_text_clips_horizontally():
    c = Canvas(5, 1)
    c.text(3, 0, "hello")  # only 'he' fits
    assert c.to_text().plain == "   he"


def test_canvas_resize_clears_state():
    c = Canvas(3, 1)
    c.set(0, 0, "a")
    c.resize(2, 2)
    assert "a" not in c.to_text().plain
    assert c.width == 2 and c.height == 2


def test_canvas_to_text_rowcount():
    c = Canvas(4, 3)
    rendered = c.to_text().plain
    # Three rows separated by 2 newlines.
    assert rendered.count("\n") == 2


def test_canvas_coalesces_shared_and_equal_styles_without_changing_spans():
    shared = Style(color="red", bgcolor="black", bold=True)
    equal = Style(color="red", bgcolor="black", bold=True)
    other = Style(color="blue")
    assert shared is not equal
    canvas = Canvas(5, 2)
    canvas.set(0, 0, "a", shared)
    canvas.set(1, 0, "b", shared)
    canvas.set(2, 0, "c", equal)
    canvas.set(3, 0, "d", other)
    canvas.set(0, 1, "e", shared)
    text = canvas.to_text()
    assert text.plain == "abcd \ne    "
    assert [(span.start, span.end, span.style) for span in text.spans] == [
        (0, 3, shared), (3, 4, other), (6, 7, shared),
    ]
    assert text.no_wrap is True
    assert text.overflow == "ignore"


def test_canvas_set_takes_first_char_only():
    c = Canvas(3, 1)
    c.set(0, 0, "abc")
    assert c.to_text().plain[0] == "a"


def test_canvas_paste_copies_cells():
    src = Canvas(3, 2)
    src.set(0, 0, "a")
    src.set(1, 0, "b")
    src.set(2, 1, "c")
    dst = Canvas(6, 4)
    dst.paste(src, 2, 1)
    rendered = dst.to_text().plain.split("\n")
    # row 1 cols 2,3 = a,b
    assert rendered[1][2] == "a"
    assert rendered[1][3] == "b"
    # row 2 col 4 = c
    assert rendered[2][4] == "c"


def test_canvas_paste_clips_at_bounds():
    src = Canvas(4, 4)
    src.fill("x")
    dst = Canvas(3, 3)
    # Paste with offset that puts most of src out of bounds — must not crash.
    dst.paste(src, 2, 2)
    rendered = dst.to_text().plain.split("\n")
    # Only cell (2,2) should be 'x'; rest are spaces.
    assert rendered[2][2] == "x"


def test_scene_registry_populated():
    # Triggers all @register decorators.
    from javalamp import scenes  # noqa: F401
    from javalamp.scene import SCENES

    expected = {
        "matrix", "starfield", "donut", "aquarium",
        "java", "marquee", "fireworks", "pipes",
        "pollock", "twombly", "bacchus",
        "buddy", "konami",
    }
    assert expected.issubset(set(SCENES))


def test_public_scene_metadata_contract():
    from javalamp import scenes  # noqa: F401
    from javalamp.scene import SCENES

    for name, cls in SCENES.items():
        if name == "konami":
            continue
        assert name == name.lower()
        assert cls.title
        assert cls.description


@pytest.mark.parametrize("text, expected", [
    ("5s", 5.0),
    ("90s", 90.0),
    ("2m", 120.0),
    ("1.5h", 5400.0),
    ("1d", 86400.0),
    ("10", 10.0),  # bare number defaults to seconds
    (None, None),
    ("", None),
])
def test_parse_duration_ok(text, expected):
    assert parse_duration(text) == expected


def test_parse_duration_bad_input():
    with pytest.raises(ValueError):
        parse_duration("forever")


@pytest.mark.parametrize("width,height", [(24, 8), (80, 24), (120, 40)])
def test_all_public_scenes_render_at_common_terminal_sizes(width, height):
    """Every public scene survives setup() + a few update() calls at common sizes."""
    import random

    from javalamp import scenes  # noqa: F401
    from javalamp.scene import SCENES
    from javalamp.theme import get_theme

    theme = get_theme("default")
    for name, cls in SCENES.items():
        if name == "konami":
            continue
        rng = random.Random(42)
        scene = cls(width=width, height=height, theme=theme, rng=rng,
                    message="test message")
        for f in range(3):
            scene.update(f, 1 / 24)
        rendered = scene.render()
        assert rendered is not None


def test_all_public_scenes_survive_all_themes():
    import random

    from javalamp import scenes  # noqa: F401
    from javalamp.scene import SCENES
    from javalamp.theme import get_theme, theme_names

    for name, cls in SCENES.items():
        if name == "konami":
            continue
        for theme_name in theme_names():
            rng = random.Random(42)
            scene = cls(width=60, height=18, theme=get_theme(theme_name),
                        rng=rng, message="test message")
            for f in range(3):
                scene.update(f, 1 / 24)
            assert scene.render() is not None


def test_buddy_cycles_through_animated_states():
    import random

    from javalamp.scenes.buddy import BuddyScene
    from javalamp.theme import get_theme

    scene = BuddyScene(80, 24, get_theme("default"), random.Random(42))

    scene.update(0, 0)
    awake = scene.render().plain
    cx, eye_y, eye_spacing, eye_radius_x, eye_radius_y, *_ = scene._layout()
    left_eye = (
        round(cx - eye_spacing / 2),
        round(eye_y),
    )

    assert len(set(awake) & set(".:-=+*#%@")) >= 5
    assert awake.splitlines()[left_eye[1]][left_eye[0]] in ".:-=+*#%@"

    scene.is_blinking = True
    scene.blink_time = scene.BLINK_FOR / 2
    scene.update(1, 0)
    assert scene.is_blinking
    blinking = scene.render().plain
    assert blinking.splitlines()[left_eye[1]][left_eye[0]] in ".:-=+*#%@"
    assert sum(char != " " for char in blinking) < sum(char != " " for char in awake)

    scene.is_blinking = False
    scene.next_blink = 5
    scene.next_sparkle = 0
    scene.update(2, 1 / 24)
    assert scene.is_sparkling
    sparkling = scene.render().plain
    assert sparkling != awake
    assert sparkling.splitlines()[left_eye[1]][left_eye[0]] in ":-=+*#%@"

    scene.awake_time = scene.SLEEP_AFTER
    scene.update(3, 1 / 24)
    assert scene.is_sleeping
    sleeping = scene.render().plain
    assert sum(char != " " for char in sleeping) < sum(char != " " for char in awake)

    scene.sleep_time = scene.SLEEP_FOR
    scene.update(4, 1 / 24)
    assert not scene.is_sleeping
    assert scene.render().plain.splitlines()[left_eye[1]][left_eye[0]] in ".:-=+*#%@"


def test_buddy_uses_approved_mock_geometry_and_animates():
    import random

    from javalamp.scenes.buddy import BuddyScene
    from javalamp.theme import get_theme

    scene = BuddyScene(80, 24, get_theme("default"), random.Random(42))
    scene.update(0, 0)
    first = scene.render().plain
    face_chars = [char for char in first if char in ".:-=+*#%@"]
    (
        _cx,
        _eye_y,
        eye_spacing,
        eye_radius_x,
        eye_radius_y,
        mouth_width,
        _mouth_top,
        _mouth_depth,
    ) = scene._layout()

    assert eye_spacing == pytest.approx(80 * 40 * 1.16 / 120)
    assert eye_radius_x == pytest.approx(80 * 96 * 1.16 / 1200)
    assert eye_radius_y == pytest.approx(24 * 96 * 1.16 / 720)
    assert eye_radius_x / eye_radius_y == pytest.approx(2.0)
    assert mouth_width == pytest.approx(80 * 250 * 1.16 / 1200)
    assert 130 < len(face_chars) < 300
    assert len(set(face_chars)) >= 6
    rows = first.splitlines()
    assert all(char == " " for char in rows[scene.height // 2][:10])

    scene.update(1, 0.5)
    second = scene.render().plain
    assert second != first
    assert len(set(second) & set(".:-=+*#%@")) >= 6
    assert sum(a != b for a, b in zip(first, second, strict=True)) > 30


def test_user_scene_loader_honors_env_dir(tmp_path, monkeypatch):
    import os
    import subprocess
    import sys

    scene_dir = tmp_path / "scenes"
    scene_dir.mkdir()
    scene_file = scene_dir / "glow.py"
    scene_file.write_text(
        """
from javalamp.scene import Scene, register

@register
class GlowScene(Scene):
    name = "glow"
    title = "Glow"
    description = "Env-loaded test scene."

    def update(self, frame, dt):
        self.canvas.clear()
        self.canvas.text(0, 0, "glow")
""",
        encoding="utf-8",
    )

    env = os.environ.copy()
    env["JAVALAMP_SCENES_DIR"] = str(scene_dir)
    src_dir = str((tmp_path.cwd() / "src").resolve())
    env["PYTHONPATH"] = (
        src_dir if not env.get("PYTHONPATH") else f"{src_dir}{os.pathsep}{env['PYTHONPATH']}"
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "from javalamp import scenes; from javalamp.scene import SCENES; "
            "raise SystemExit(0 if 'glow' in SCENES else 1)",
        ],
        env=env,
        check=False,
    )
    assert result.returncode == 0


def test_picker_t_cycles_theme():
    import random

    from javalamp import scenes  # noqa: F401
    from javalamp.picker import Picker
    from javalamp.scene import SCENES
    from javalamp.theme import get_theme, theme_names

    picker = Picker([SCENES["java"]], get_theme("sunset"), random.Random(42))
    picker._term_size = lambda: (80, 24)
    picker._compute_layout()
    picker._handle("t")

    names = theme_names()
    expected = names[(names.index("sunset") + 1) % len(names)]
    assert picker.theme.name == expected
    assert picker.tiles[1].scene is not None
    assert picker.tiles[1].scene.theme.name == expected
