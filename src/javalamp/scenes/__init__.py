"""Built-in scenes are imported here for their @register side effects.

Users can add their own scenes by dropping `.py` files into
``~/.config/javalamp/scenes/`` (or the path in
``$JAVALAMP_SCENES_DIR``). Each file should declare a Scene
subclass decorated with ``@register`` from ``javalamp.scene``.
See ``CONTRIBUTING.md`` for a template and a worked example.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import sys
import warnings
from pathlib import Path

from javalamp.scenes import (  # noqa: F401
    aquarium,
    bacchus,
    donut,
    fireworks,
    konami,
    marquee,
    matrix,
    pipes,
    plasma,
    pollock,
    starfield,
    twombly,
)


def _user_scene_dir() -> Path:
    override = os.environ.get("JAVALAMP_SCENES_DIR")
    if override:
        return Path(override).expanduser()
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg).expanduser() if xdg else Path.home() / ".config"
    return base / "javalamp" / "scenes"


def _load_user_scenes() -> None:
    """Import every .py file in the user scenes dir so its @register fires.

    Failures are warned, not raised — one broken scene shouldn't take the
    whole tool down. Files starting with ``_`` are skipped (allows shared
    helpers).
    """
    user_dir = _user_scene_dir()
    if not user_dir.is_dir():
        return
    for py in sorted(user_dir.glob("*.py")):
        if py.name.startswith("_"):
            continue
        # Use a unique module name so multiple sessions don't clash and so
        # we don't shadow a built-in module.
        mod_name = f"javalamp_user_scenes.{py.stem}"
        try:
            spec = importlib.util.spec_from_file_location(mod_name, py)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            sys.modules[mod_name] = module
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001 — keep the tool running
            warnings.warn(
                f"javalamp: failed to load user scene {py.name}: {exc}",
                stacklevel=2,
            )


_load_user_scenes()
