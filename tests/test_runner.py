"""Finite animation-loop tests without terminal IO or background refresh."""

import os
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import javalamp.picker as picker_module
import javalamp.runner as runner_module
from javalamp.picker import QUIT, Picker
from javalamp.runner import Runner
from javalamp.scene import Scene
from javalamp.scenes.plasma import PlasmaScene


@pytest.fixture
def animation_loop(monkeypatch):
    state = SimpleNamespace(now=0.0, clock_reads=0, sleeps=[], updates=[], lives=[])

    def monotonic():
        state.clock_reads += 1
        assert state.clock_reads < 256, "loop exceeded its finite clock-read budget"
        return state.now

    def sleep(seconds):
        assert seconds > 0
        state.sleeps.append(seconds)
        state.now += seconds

    class ProbeScene(Scene):
        name = "probe"

        def update(self, frame, dt):
            state.updates.append((self.name, frame, dt, self.theme.name))
            state.now += 0.01

        def render(self):
            state.now += 0.005
            return super().render()

    class OtherScene(ProbeScene):
        name = "other"

    class ManualLive:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.frames = []
            state.lives.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def update(self, renderable, refresh=False):
            assert refresh is True
            self.frames.append(renderable)
            state.now += 0.02

    monkeypatch.setattr(runner_module.time, "monotonic", monotonic)
    monkeypatch.setattr(runner_module.time, "sleep", sleep)
    monkeypatch.setattr(runner_module, "Live", ManualLive)
    monkeypatch.setattr(runner_module, "keep_awake", lambda enabled: nullcontext())
    monkeypatch.setattr(runner_module, "cbreak_stdin", lambda: nullcontext(42))
    monkeypatch.setattr(runner_module, "read_key", lambda fd: None)
    runner = Runner(
        [PlasmaScene.name], theme_name="mono", fps=12, caffeinate=False, duration=0.24, seed=42
    )
    runner.scene_classes = [ProbeScene, OtherScene]
    monkeypatch.setattr(runner, "_install_handlers", lambda: None)
    monkeypatch.setattr(runner, "_term_size", lambda: (10, 5))
    state.runner = runner
    return state


def test_runner_refreshes_once_per_tick_and_budgets_render_time(animation_loop):
    state = animation_loop
    assert state.runner.run() == 0
    live = state.lives[0]
    assert live.options["auto_refresh"] is False
    assert live.options["refresh_per_second"] == 12
    assert live.options["screen"] is True
    assert len(live.frames) == len(state.updates) == 4
    assert [update[1] for update in state.updates] == [0, 1, 2, 3]
    assert all(update[2] == 1 / 12 for update in state.updates)
    assert state.sleeps == pytest.approx([1 / 12 - 0.035] * 3)
    for frame in live.frames:
        footer = list(frame.renderables)[-1]
        assert "javalamp" in footer.plain and "theme:mono" in footer.plain
        assert "q quit" in footer.plain and "space pause" in footer.plain


def test_runner_preserves_pause_theme_next_and_quit(animation_loop, monkeypatch):
    state = animation_loop
    keys = iter((" ", None, " ", "t", None, "n", None, "q", None))
    monkeypatch.setattr(runner_module, "read_key", lambda fd: next(keys))
    state.runner.duration = 5
    state.runner._wipe_transition = Mock()
    original_theme = state.runner.theme.name
    assert state.runner.run() == 0
    assert state.runner._stop is True
    assert state.runner.theme.name != original_theme
    assert [update[0] for update in state.updates] == ["probe", "probe", "other"]
    assert [update[1] for update in state.updates] == [0, 1, 0]
    state.runner._wipe_transition.assert_called_once()
    frames = state.lives[0].frames
    assert "PAUSED" in list(frames[0].renderables)[-1].plain
    assert "PAUSED" not in list(frames[1].renderables)[-1].plain


def test_runner_reserves_exactly_one_footer_row(monkeypatch):
    monkeypatch.setattr(
        runner_module.shutil, "get_terminal_size", lambda fallback: os.terminal_size((240, 67))
    )
    assert Runner([PlasmaScene.name])._term_size() == (240, 66)


def test_runner_resize_is_applied_before_update(animation_loop, monkeypatch):
    state = animation_loop
    state.runner._resize_pending = True
    scene = state.runner._build_scene(state.runner.scene_classes[0])
    resize = Mock(wraps=scene.resize)
    monkeypatch.setattr(scene, "resize", resize)
    monkeypatch.setattr(state.runner, "_build_scene", lambda cls: scene)
    monkeypatch.setattr(state.runner, "_term_size", lambda: (17, 7))
    state.runner.run()
    resize.assert_called_once_with(17, 7)
    assert (scene.canvas.width, scene.canvas.height) == (17, 7)


def test_picker_explicitly_refreshes_with_manual_live(animation_loop, monkeypatch):
    state = animation_loop
    picker = Picker(state.runner.scene_classes, state.runner.theme, state.runner.rng)
    monkeypatch.setattr(picker, "_compute_layout", lambda: None)
    monkeypatch.setattr(picker, "update", lambda dt: None)
    monkeypatch.setattr(picker, "render", lambda: "picker frame")
    keys = iter((None, "q"))
    monkeypatch.setattr(picker_module, "read_key", lambda fd: next(keys))
    live = runner_module.Live(auto_refresh=False)
    assert picker.run(live, 42) is QUIT
    assert live.frames == ["picker frame"]
