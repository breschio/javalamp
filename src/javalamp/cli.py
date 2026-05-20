"""javalamp command-line interface.

Positional SCENE is optional:
    javalamp                  -> cycle through all scenes
    javalamp matrix           -> play one scene
    javalamp -l               -> list scenes
    javalamp new-scene lava   -> scaffold a user scene
    javalamp check-scene lava -> validate a scene
"""

from __future__ import annotations

import re
import sys
import textwrap
import time
from pathlib import Path

import click
from rich.box import ROUNDED
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

# Importing the scenes package triggers @register on every scene module.
from javalamp import scenes  # noqa: F401  (side-effect import)
from javalamp.runner import Runner, parse_duration
from javalamp.scene import SCENE_ALIASES, SCENES, Scene, all_scenes
from javalamp.theme import get_theme, theme_names

_console = Console()
_SLUG_RE = re.compile(r"^[a-z][a-z0-9_]*$")


def _splash(theme_name: str) -> None:
    theme = get_theme(theme_name)
    title = Text("javalamp", style=f"bold {theme.accent}")
    sub = Text("animated ascii for the away-from-keyboard hours",
               style=f"italic {theme.fg}")
    keys = Text(
        "press q to quit · n next scene · space pause · t cycle theme",
        style=theme.dim,
    )
    body = Text("\n").join([title, sub, Text(""), keys])
    _console.print(Panel(body, border_style=theme.accent2, box=ROUNDED, padding=(1, 4)))


def _print_scene_list() -> None:
    table = Table(title="javalamp scenes", box=ROUNDED, header_style="bold")
    table.add_column("name", style="cyan", no_wrap=True)
    table.add_column("title")
    table.add_column("description", style="dim")
    for cls in all_scenes():
        if cls.name == "konami":
            continue
        table.add_row(cls.name, cls.title, cls.description or "—")
    _console.print(table)
    _console.print(f"\nThemes: {', '.join(theme_names())}")
    _console.print("Hotkeys while running:  q quit  ·  n next  ·  space pause  ·  t cycle theme")


def _user_scene_dir() -> Path:
    from javalamp.scenes import _user_scene_dir as scenes_user_scene_dir

    return scenes_user_scene_dir()


def _class_name_from_slug(slug: str) -> str:
    return "".join(part.capitalize() for part in slug.split("_")) + "Scene"


def _scene_template(slug: str) -> str:
    title = slug.replace("_", " ").title()
    class_name = _class_name_from_slug(slug)
    return textwrap.dedent(f'''\
        """{title} — a custom javalamp scene."""

        from rich.style import Style

        from javalamp.scene import Scene, register


        @register
        class {class_name}(Scene):
            name = "{slug}"
            title = "{title}"
            description = "A new custom scene."

            def setup(self) -> None:
                self.x = 0
                self.dx = 1

            def update(self, frame: int, dt: float) -> None:
                self.canvas.clear()
                msg = "{slug}"
                self.x += self.dx
                if self.x <= 0 or self.x + len(msg) >= self.width:
                    self.dx *= -1
                self.canvas.text(
                    self.x,
                    self.height // 2,
                    msg,
                    Style(color=self.theme.fg, bgcolor=self.theme.bg, bold=True),
                )
        ''')


def _new_scene(slug: str) -> int:
    if not _SLUG_RE.fullmatch(slug):
        click.echo(
            "error: scene names must be lowercase slugs: letters, numbers, underscores; "
            "start with a letter.",
            err=True,
        )
        return 2
    if slug in SCENES or slug in SCENE_ALIASES:
        click.echo(f"error: scene '{slug}' already exists.", err=True)
        return 2

    scene_dir = _user_scene_dir()
    scene_dir.mkdir(parents=True, exist_ok=True)
    scene_path = scene_dir / f"{slug}.py"
    if scene_path.exists():
        click.echo(f"error: {scene_path} already exists.", err=True)
        return 2

    scene_path.write_text(_scene_template(slug), encoding="utf-8")
    click.echo(f"created {scene_path}")
    click.echo(f"try it with: javalamp {slug}")
    return 0


def _check_scene_metadata(name: str, cls: type[Scene]) -> list[str]:
    problems: list[str] = []
    if not _SLUG_RE.fullmatch(name):
        problems.append("name must be a lowercase slug")
    if not cls.title:
        problems.append("title is required")
    if not cls.description:
        problems.append("description is required")
    return problems


def _check_scene(name: str) -> int:
    if name in SCENE_ALIASES:
        name = SCENE_ALIASES[name]

    if name not in SCENES:
        available = ", ".join(n for n in sorted(set(SCENES) | set(SCENE_ALIASES)) if n != "konami")
        click.echo(f"error: unknown scene '{name}'.", err=True)
        click.echo(f"       try one of: {available}", err=True)
        return 2

    import random

    cls = SCENES[name]
    problems = _check_scene_metadata(name, cls)
    sizes = [(24, 8), (80, 24), (120, 40)]
    for theme_name in theme_names():
        theme = get_theme(theme_name)
        for width, height in sizes:
            try:
                scene_obj = cls(
                    width=width,
                    height=height,
                    theme=theme,
                    rng=random.Random(42),
                    message="test message",
                )
                for frame in range(3):
                    scene_obj.update(frame, 1 / 24)
                if scene_obj.render() is None:
                    problems.append(f"{theme_name} {width}x{height}: render returned None")
            except Exception as exc:  # noqa: BLE001 - CLI should report all scene failures cleanly
                problems.append(f"{theme_name} {width}x{height}: {exc}")

    if problems:
        click.echo(f"{name}: failed")
        for problem in problems:
            click.echo(f"- {problem}")
        return 1

    click.echo(f"{name}: ok ({len(theme_names())} themes x {len(sizes)} sizes)")
    return 0


class _FriendlyCommand(click.Command):
    """Catches the v0 syntax (`javalamp play matrix`) and points at the new one."""

    def parse_args(self, ctx, args):
        if args and args[0] == "play":
            click.echo(
                "the 'play' subcommand was removed — just use `javalamp <scene>` "
                "(e.g. `javalamp matrix`).",
                err=True,
            )
            ctx.exit(2)
        return super().parse_args(ctx, args)


@click.command(cls=_FriendlyCommand,
               context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("scene", required=False)
@click.argument("scene_arg", required=False)
@click.option("-l", "--list", "list_only", is_flag=True, default=False,
              help="List available scenes and exit.")
@click.option("-t", "--theme", "theme_name", default="sunset",
              show_default=True, type=click.Choice(theme_names()),
              metavar="NAME",
              help="Color palette — applied to every scene in the session.")
@click.option("-d", "--duration", default=None, type=str, metavar="DUR",
              help="Auto-exit after a duration (e.g. 90s, 5m, 1h).")
@click.option("-i", "--interval", default=60.0, show_default=True, type=float,
              metavar="SEC", help="Seconds per scene when cycling.")
@click.option("-m", "--message", default=None, type=str,
              help="Custom away-message used by the marquee scene.")
@click.option("-f", "--fps", default=24, show_default=True, type=int,
              help="Animation frame rate.")
@click.option("-s", "--seed", default=None, type=int, help="RNG seed.")
@click.option("--no-caffeinate", is_flag=True, default=False,
              help="Don't keep the display awake (macOS only).")
@click.option("--no-splash", is_flag=True, default=False,
              help="Skip the startup splash screen.")
@click.option("--cycle", "cycle_mode", is_flag=True, default=False,
              help="Skip the picker and cycle through every scene "
                   "(the original v0 behavior).")
@click.version_option(package_name="javalamp", prog_name="javalamp")
def main(
    scene: str | None,
    scene_arg: str | None,
    list_only: bool,
    theme_name: str,
    duration: str | None,
    interval: float,
    message: str | None,
    fps: int,
    seed: int | None,
    no_caffeinate: bool,
    no_splash: bool,
    cycle_mode: bool,
) -> None:
    """javalamp — animated ASCII screensaver.

    Run with no SCENE to open the picker (arrow keys to navigate, enter to
    play). Pass a scene name (e.g. `javalamp matrix`) to skip the picker and
    play directly. Use `-l` to list scenes, `--cycle` to auto-rotate
    every scene without the picker.
    """
    if list_only:
        _print_scene_list()
        return

    if scene == "new-scene":
        if not scene_arg:
            click.echo("error: usage: javalamp new-scene <slug>", err=True)
            sys.exit(2)
        sys.exit(_new_scene(scene_arg))

    if scene == "check-scene":
        if not scene_arg:
            click.echo("error: usage: javalamp check-scene <slug>", err=True)
            sys.exit(2)
        sys.exit(_check_scene(scene_arg))

    if scene_arg is not None:
        click.echo(f"error: unexpected argument '{scene_arg}'", err=True)
        sys.exit(2)

    # Friendly fallback: `javalamp list` -> show the list (back-compat with v0).
    if scene == "list":
        _print_scene_list()
        return

    # Validate scene name early so we don't show a splash before erroring.
    if scene is not None and scene in SCENE_ALIASES:
        scene = SCENE_ALIASES[scene]

    if scene is not None and scene not in SCENES:
        available = ", ".join(n for n in sorted(set(SCENES) | set(SCENE_ALIASES)) if n != "konami")
        # Suggest the closest match if there's an obvious typo.
        from difflib import get_close_matches
        suggestion = get_close_matches(scene, list(SCENES), n=1)
        hint = f" Did you mean '{suggestion[0]}'?" if suggestion else ""
        click.echo(f"error: unknown scene '{scene}'.{hint}", err=True)
        click.echo(f"       try one of: {available}", err=True)
        click.echo("       or run: javalamp -l", err=True)
        sys.exit(2)

    try:
        dur_s = parse_duration(duration)
    except ValueError as e:
        click.echo(f"error: {e}", err=True)
        sys.exit(2)

    # Picker is the new default when the user gave no scene and didn't ask
    # for explicit cycle mode.
    show_picker = scene is None and not cycle_mode

    # Splash competes for screen time with the picker — skip it when the
    # picker is going to show, since the picker IS the welcome screen.
    if not no_splash and not show_picker:
        _splash(theme_name)
        time.sleep(1.0)

    runner = Runner(
        scene_names=[scene] if scene else None,
        theme_name=theme_name,
        fps=fps,
        interval=interval,
        duration=dur_s,
        message=message,
        seed=seed,
        caffeinate=not no_caffeinate,
        show_picker=show_picker,
    )
    sys.exit(runner.run())


if __name__ == "__main__":
    main()
