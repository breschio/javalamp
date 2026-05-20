"""Render deterministic README media from javalamp itself."""

from __future__ import annotations

import random
from io import StringIO
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from rich.console import Console

from javalamp import scenes  # noqa: F401
from javalamp.picker import Picker
from javalamp.runner import _PICKER_ORDER
from javalamp.scene import SCENES
from javalamp.theme import get_theme

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
ASSETS.mkdir(exist_ok=True)


def render_picker_svg() -> None:
    width = 132
    height = 33
    menu_scenes = sorted(
        [cls for cls in SCENES.values() if cls.name != "konami"],
        key=lambda cls: (_PICKER_ORDER.get(cls.name, 99), cls.title),
    )
    picker = Picker(menu_scenes, get_theme("sunset"), random.Random(7))
    picker._term_size = lambda: (width, height)  # noqa: SLF001
    picker._compute_layout()  # noqa: SLF001
    for _ in range(3):
        picker.update(1 / 12)

    console = Console(
        record=True,
        file=StringIO(),
        width=width,
        height=height,
        color_system="truecolor",
        force_terminal=True,
        legacy_windows=False,
    )
    console.print(picker.render())
    (ASSETS / "picker.svg").write_text(
        console.export_svg(title="javalamp picker"),
        encoding="utf-8",
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


def render_java_gif() -> None:
    theme = get_theme("sunset")
    scene = SCENES["java"](80, 18, theme, random.Random(11))
    font = _font(15)
    bbox = font.getbbox("M")
    cell_w = bbox[2] - bbox[0]
    cell_h = bbox[3] - bbox[1] + 3
    pad_x = 18
    pad_y = 16
    image_w = scene.width * cell_w + pad_x * 2
    image_h = scene.height * cell_h + pad_y * 2
    bg = _hex_to_rgb(theme.bg)

    frames: list[Image.Image] = []
    for frame in range(30):
        scene.update(frame, 1 / 12)
        image = Image.new("RGB", (image_w, image_h), bg)
        draw = ImageDraw.Draw(image)
        draw.text((pad_x, 4), "javalamp java -t sunset", fill=_hex_to_rgb(theme.fg), font=font)
        for y, row in enumerate(scene.canvas._cells):  # noqa: SLF001
            for x, (ch, style) in enumerate(row):
                if ch == " ":
                    continue
                color = theme.fg
                if style and style.color:
                    color = style.color.triplet.hex
                draw.text(
                    (pad_x + x * cell_w, pad_y + y * cell_h),
                    ch,
                    fill=_hex_to_rgb(color),
                    font=font,
                )
        frames.append(image)

    frames[0].save(
        ASSETS / "java-demo.gif",
        save_all=True,
        append_images=frames[1:],
        duration=80,
        loop=0,
        optimize=True,
    )


def main() -> None:
    render_picker_svg()
    render_java_gif()


if __name__ == "__main__":
    main()
