"""Finite captured-output plasma benchmark; use external resource limits."""

from __future__ import annotations

import argparse
import json
import random
import statistics
import time
from contextlib import nullcontext
from unittest.mock import patch

from rich.console import Console, Group
from rich.live import Live

import javalamp
from javalamp.runner import Runner
from javalamp.scenes.plasma import PlasmaScene
from javalamp.theme import get_theme, theme_names


class CountingOutput:
    encoding = "utf-8"

    def __init__(self) -> None:
        self.characters = 0

    def write(self, text: str) -> int:
        self.characters += len(text)
        return len(text)

    def flush(self) -> None:
        pass

    def isatty(self) -> bool:
        return True


def measure(operation, frames: int) -> dict:
    cpu_samples = []
    wall_samples = []
    for _ in range(frames):
        wall_start = time.perf_counter()
        cpu_start = time.process_time()
        operation()
        cpu_samples.append((time.process_time() - cpu_start) * 1000)
        wall_samples.append((time.perf_counter() - wall_start) * 1000)
    return {
        "cpu_ms_mean": statistics.mean(cpu_samples),
        "cpu_ms_median": statistics.median(cpu_samples),
        "wall_ms_mean": statistics.mean(wall_samples),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frames", type=int, default=12, choices=range(1, 49))
    parser.add_argument("--seconds", type=int, default=3, choices=(1, 3, 12))
    parser.add_argument("--width", type=int, default=240, choices=(80, 160, 240))
    parser.add_argument("--height", type=int, default=67, choices=(24, 40, 67))
    parser.add_argument("--fps", type=int, default=12, choices=(12, 24, 30))
    parser.add_argument("--theme", default="mono", choices=theme_names())
    args = parser.parse_args()
    output = CountingOutput()
    console = Console(
        file=output,
        force_terminal=True,
        color_system="standard",
        width=args.width,
        height=args.height,
        legacy_windows=False,
    )
    scene = PlasmaScene(args.width, args.height - 1, get_theme(args.theme), random.Random(42))
    runner = Runner(
        ["java"],
        theme_name=args.theme,
        fps=args.fps,
        caffeinate=False,
        duration=args.seconds,
        seed=42,
    )
    runner.console = console
    frame = 0

    def update():
        nonlocal frame
        scene.update(frame, 1 / args.fps)
        frame += 1

    update()
    scene.render()
    results = {
        "dimensions": [args.width, args.height],
        "fps": args.fps,
        "theme": args.theme,
        "frames_per_stage": args.frames,
        "source": javalamp.__file__,
        "output": "counting sink, standard ANSI",
    }
    results["update"] = measure(update, args.frames)
    results["scene_render"] = measure(scene.render, args.frames)
    renderable = Group(scene.render(), runner._footer(scene))
    with Live(renderable, console=console, screen=True, auto_refresh=False) as live:
        results["rich_live_refresh"] = measure(live.refresh, args.frames)
    runner._install_handlers = lambda: None
    runner._build_scene = lambda cls: scene
    original_update = scene.update
    updates = 0

    def counted_update(frame, dt):
        nonlocal updates
        updates += 1
        original_update(frame, dt)

    scene.update = counted_update
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    with (
        patch("javalamp.runner.cbreak_stdin", return_value=nullcontext(None)),
        patch("javalamp.runner.read_key", return_value=None),
    ):
        runner.run()
    wall = time.perf_counter() - wall_start
    cpu = time.process_time() - cpu_start
    results["runner"] = {
        "cpu_seconds": cpu,
        "wall_seconds": wall,
        "logical_cpu_percent": 100 * cpu / wall,
        "updates": updates,
        "updates_per_second": updates / wall,
    }
    results["captured_characters"] = output.characters
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
