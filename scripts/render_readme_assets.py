"""Render deterministic README media from javalamp itself."""

from __future__ import annotations

import random
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from javalamp import scenes  # noqa: F401
from javalamp.picker import Picker
from javalamp.runner import _PICKER_ORDER
from javalamp.scene import SCENES
from javalamp.theme import get_theme

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)

TERM_COLS = 132
TERM_ROWS = 33
FONT_SIZE = 12
FPS = 10
SECONDS_PER_VIEW = 3


def _menu_scenes() -> list[type]:
    return sorted(
        [cls for cls in SCENES.values() if cls.name != "konami"],
        key=lambda cls: (_PICKER_ORDER.get(cls.name, 99), cls.title),
    )


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/Monaco.ttf",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _hex_to_rgb(color: str) -> tuple[int, int, int]:
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))


def _style_color(style, fallback: str) -> tuple[int, int, int]:
    if style and style.color:
        return _hex_to_rgb(style.color.triplet.hex)
    return _hex_to_rgb(fallback)


def _terminal_frame(
    cells,
    title: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    cell_w: int,
    cell_h: int,
    bg: tuple[int, int, int],
    fallback_fg: str,
) -> Image.Image:
    pad_x = 18
    pad_y = 16
    chrome_h = 28
    image_w = TERM_COLS * cell_w + pad_x * 2
    image_h = TERM_ROWS * cell_h + pad_y * 2 + chrome_h
    chrome_bg = (21, 24, 30)
    border = (64, 68, 78)

    image = Image.new("RGB", (image_w, image_h), (13, 17, 23))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, image_w - 1, image_h - 1),
        radius=8,
        fill=bg,
        outline=border,
        width=1,
    )
    draw.rounded_rectangle(
        (0, 0, image_w - 1, chrome_h),
        radius=8,
        fill=chrome_bg,
        outline=border,
        width=1,
    )
    draw.rectangle((0, chrome_h - 8, image_w - 1, chrome_h), fill=chrome_bg)
    for i, color in enumerate(((255, 95, 86), (255, 189, 46), (39, 201, 63))):
        x = 14 + i * 18
        draw.ellipse((x, 9, x + 10, 19), fill=color)
    title_w = draw.textlength(title, font=font)
    draw.text(
        ((image_w - title_w) / 2, 6),
        title,
        fill=(198, 200, 206),
        font=font,
    )

    for y, row in enumerate(cells):
        if y >= TERM_ROWS:
            break
        for x, (ch, style) in enumerate(row[:TERM_COLS]):
            if ch == " ":
                continue
            draw.text(
                (pad_x + x * cell_w, chrome_h + pad_y + y * cell_h),
                ch,
                fill=_style_color(style, fallback_fg),
                font=font,
            )
    return image


def _picker_cells(frame: int):
    picker = Picker(_menu_scenes(), get_theme("sunset"), random.Random(7))
    picker._term_size = lambda: (TERM_COLS, TERM_ROWS)  # noqa: SLF001
    picker._compute_layout()  # noqa: SLF001
    for _ in range(frame + 1):
        picker.update(1 / FPS)
    picker.render()
    return picker.canvas._cells  # noqa: SLF001


def _java_cells(frame: int):
    theme = get_theme("sunset")
    scene = SCENES["java"](TERM_COLS, TERM_ROWS, theme, random.Random(11))
    for f in range(frame + 1):
        scene.update(f, 1 / FPS)
    return scene.canvas._cells  # noqa: SLF001


def render_readme_gif() -> None:
    theme = get_theme("sunset")
    font = _font(FONT_SIZE)
    bbox = font.getbbox("M")
    cell_w = bbox[2] - bbox[0]
    cell_h = bbox[3] - bbox[1] + 3
    frames: list[Image.Image] = []

    frame_count = FPS * SECONDS_PER_VIEW
    for frame in range(frame_count):
        frames.append(
            _terminal_frame(
                _picker_cells(frame),
                "javalamp picker",
                font,
                cell_w,
                cell_h,
                _hex_to_rgb(theme.bg),
                theme.fg,
            )
        )
    for frame in range(frame_count):
        frames.append(
            _terminal_frame(
                _java_cells(frame),
                "javalamp java",
                font,
                cell_w,
                cell_h,
                _hex_to_rgb(theme.bg),
                theme.fg,
            )
        )

    frames[0].save(
        ASSETS / "javalamp-demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / FPS),
        loop=0,
        optimize=True,
    )


def main() -> None:
    render_readme_gif()


if __name__ == "__main__":
    main()
