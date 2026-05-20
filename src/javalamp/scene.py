"""Scene base class and registry."""

from __future__ import annotations

import random
from typing import ClassVar

from rich.console import RenderableType

from javalamp.canvas import Canvas
from javalamp.theme import Theme


class Scene:
    """Base class for all animations.

    Subclasses must set ``name`` and ``title`` and implement ``update``/``render``.
    Most scenes will keep a single ``Canvas`` and rebuild it each frame.
    """

    name: ClassVar[str] = ""
    title: ClassVar[str] = ""
    description: ClassVar[str] = ""

    def __init__(self, width: int, height: int, theme: Theme, rng: random.Random,
                 message: str | None = None) -> None:
        self.width = width
        self.height = height
        self.theme = theme
        self.rng = rng
        self.message = message
        self.canvas = Canvas(width, height, default_bg=theme.bg)
        self.setup()

    # Subclass hooks ---------------------------------------------------------

    def setup(self) -> None:
        """Called once after construction, with width/height/theme available."""

    def resize(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.canvas.resize(width, height)
        self.setup()  # re-seed any state that depends on dimensions

    def update(self, frame: int, dt: float) -> None:
        raise NotImplementedError

    def render(self) -> RenderableType:
        return self.canvas.to_text()


# Registry ------------------------------------------------------------------

SCENES: dict[str, type[Scene]] = {}
SCENE_ALIASES: dict[str, str] = {
    "plasma": "java",
}


def register(cls: type[Scene]) -> type[Scene]:
    if not cls.name:
        raise ValueError(f"Scene {cls.__name__} missing 'name' class attribute")
    if cls.name in SCENES:
        raise ValueError(f"Scene name {cls.name!r} already registered")
    SCENES[cls.name] = cls
    return cls


def all_scenes() -> list[type[Scene]]:
    return [SCENES[name] for name in sorted(SCENES)]


def get_scene(name: str) -> type[Scene]:
    name = SCENE_ALIASES.get(name, name)
    if name not in SCENES:
        available = sorted(set(SCENES) | set(SCENE_ALIASES))
        raise KeyError(f"Unknown scene {name!r}. Available: {', '.join(available)}")
    return SCENES[name]
