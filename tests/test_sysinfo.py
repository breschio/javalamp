"""System-stat regressions use fixtures, never real hardware or daemons."""

import io
import subprocess
from concurrent.futures import Future
from contextlib import nullcontext
from pathlib import Path
from threading import Event
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import pytest
from click.testing import CliRunner

import javalamp.cli as cli_module
import javalamp.runner as runner_module
import javalamp.sysinfo as sysinfo_module
from javalamp.picker import QUIT
from javalamp.runner import Runner
from javalamp.scenes.plasma import PlasmaScene
from javalamp.sysinfo import SysInfoCollector, SystemStats


def test_default_footer_is_unchanged():
    runner = Runner([PlasmaScene.name], theme_name="mono")
    assert runner._sysinfo is None
    scene = runner._build_scene(PlasmaScene)
    assert runner._footer(scene).plain == (
        f" \u2726 javalamp \u00b7 {scene.title} \u00b7 theme:mono "
        "\u00b7 q quit \u00b7 n next \u00b7 space pause \u00b7 t theme"
    )


def test_missing_stats_fall_back_to_default_footer():
    runner = Runner([PlasmaScene.name], theme_name="mono")
    scene = runner._build_scene(PlasmaScene)
    expected = runner._footer(scene)
    collector = Mock(spec=SysInfoCollector)
    collector.collect.return_value = SystemStats()
    collector.format_footer.return_value = ""
    runner._sysinfo = collector
    assert runner._footer(scene) == expected


def test_stats_footer_keeps_pause_and_keyboard_hints():
    runner = Runner([PlasmaScene.name], theme_name="mono")
    collector = Mock(spec=SysInfoCollector)
    collector.collect.return_value = SystemStats(cpu_percent=25)
    collector.format_footer.return_value = "CPU 25%"
    runner._sysinfo = collector
    runner._paused = True
    footer = runner._footer(runner._build_scene(PlasmaScene))
    assert footer.plain == " CPU 25% \u2502 PAUSED \u2502 q \u00b7 n \u00b7 space \u00b7 t "
    assert footer.no_wrap is True
    assert footer.overflow == "ellipsis"


def test_cpu_percentage_excludes_guest_counters(monkeypatch):
    snapshots = iter(("cpu 100 0 0 100 0 0 0 0 50 0", "cpu 110 0 0 110 0 0 0 0 60 0"))
    monkeypatch.setattr(Path, "read_text", lambda path: next(snapshots))
    collector = SysInfoCollector()
    assert collector._read_cpu_percent() is None
    assert collector._read_cpu_percent() == 50.0


@pytest.mark.parametrize(
    "second,expected",
    [
        ("cpu 100 0 0 100", 0.0),
        ("cpu 0 0 0 0", None),
        ("cpu 110 0 0 90", None),
        ("", None),
        ("cpu malformed", None),
    ],
)
def test_cpu_handles_missing_or_reset_counters(monkeypatch, second, expected):
    snapshots = iter(("cpu 100 0 0 100", second))
    monkeypatch.setattr(Path, "read_text", lambda path: next(snapshots))
    collector = SysInfoCollector()
    assert collector._read_cpu_percent() is None
    assert collector._read_cpu_percent() == expected


@pytest.mark.parametrize(
    "text,expected",
    [
        ("MemTotal: 100 kB\nMemAvailable: 62 kB\n", 38.0),
        ("MemTotal: 100 kB\n", None),
        ("MemTotal: 0 kB\nMemAvailable: 0 kB\n", None),
        ("MemTotal: 100 kB\nMemAvailable: 200 kB\n", None),
        ("malformed", None),
    ],
)
def test_memory_readings(monkeypatch, text, expected):
    monkeypatch.setattr(Path, "read_text", lambda path: text)
    assert SysInfoCollector()._read_ram() == expected


class DockerSocket:
    def __init__(self, response):
        self.response = response
        self.closed = False
        self.request = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def settimeout(self, timeout):
        assert timeout == 1.0

    def connect(self, address):
        assert address == "/var/run/docker.sock"

    def sendall(self, request):
        self.request = request

    def makefile(self, mode):
        return io.BytesIO(self.response)


@pytest.mark.parametrize(
    "response,expected",
    [
        (b'HTTP/1.1 200 OK\r\n\r\n[{"State":"running"},{"State":"exited"}]', (1, 2)),
        (
            b"HTTP/1.1 200 OK\r\ntransfer-encoding: chunked\r\n\r\n2;ext=yes\r\n[]\r\n0\r\n\r\n",
            (0, 0),
        ),
        (b"HTTP/1.1 403 Forbidden\r\n\r\n[]", (None, None)),
        (b"HTTP/1.1 200 OK\r\n\r\n{}", (None, None)),
        (b"HTTP/1.1 200 OK\r\n\r\n[1]", (None, None)),
        (b"HTTP/1.1 200 OK\r\n\r\ninvalid", (None, None)),
        (b"HTTP/1.1 200 OK\r\n\r\n" + b" " * (1024 * 1024 + 1), (None, None)),
    ],
)
def test_docker_uses_http_parser_and_closes_socket(monkeypatch, response, expected):
    sock = DockerSocket(response)
    monkeypatch.setattr(sysinfo_module.socket, "socket", lambda *args: sock)
    assert SysInfoCollector()._read_docker() == expected
    assert sock.closed
    assert sock.request.startswith(b"GET /containers/json?all=true HTTP/1.1\r\n")


def test_docker_socket_failure_is_omitted_and_closed(monkeypatch):
    sock = DockerSocket(b"")
    sock.connect = Mock(side_effect=PermissionError)
    monkeypatch.setattr(sysinfo_module.socket, "socket", lambda *args: sock)
    assert SysInfoCollector()._read_docker() == (None, None)
    assert sock.closed


def test_zfs_is_disabled_without_selected_pool(monkeypatch):
    command = Mock(side_effect=AssertionError("unexpected subprocess"))
    monkeypatch.setattr(sysinfo_module.subprocess, "run", command)
    assert SysInfoCollector()._read_zfs() == (None, None)
    command.assert_not_called()


@pytest.mark.parametrize(
    "output,expected",
    [
        ("ONLINE\t41\n", ("ONLINE", 41)),
        ("DEGRADED\t80%\n", ("DEGRADED", 80)),
        ("", (None, None)),
        ("ONLINE\t101\n", (None, None)),
    ],
)
def test_zfs_uses_selected_pool_and_bounded_command(monkeypatch, output, expected):
    command = Mock(return_value=SimpleNamespace(returncode=0, stdout=output))
    monkeypatch.setattr(sysinfo_module.subprocess, "run", command)
    assert SysInfoCollector(zfs_pool="tank")._read_zfs() == expected
    command.assert_called_once_with(
        ["zpool", "list", "-Hp", "-o", "health,cap", "tank"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        timeout=2,
    )


@pytest.mark.parametrize("error", [FileNotFoundError(), subprocess.TimeoutExpired("zpool", 2)])
def test_zfs_failures_are_omitted(monkeypatch, error):
    monkeypatch.setattr(sysinfo_module.subprocess, "run", Mock(side_effect=error))
    assert SysInfoCollector(zfs_pool="tank")._read_zfs() == (None, None)


@pytest.mark.parametrize("pool", ["", "-a", "../tank", "tank/name"])
def test_invalid_pool_names_are_rejected(pool):
    with pytest.raises(ValueError, match="pool name"):
        SysInfoCollector(zfs_pool=pool)


def test_cache_intervals_are_independent(monkeypatch):
    clock = [0.0]
    monkeypatch.setattr(sysinfo_module.time, "monotonic", lambda: clock[0])
    with SysInfoCollector(zfs_pool="tank") as collector:
        values = {
            "_read_uptime": 60,
            "_read_cpu_percent": 25,
            "_read_cpu_temp": 52,
            "_read_ram": 38,
            "_read_gpu": (45, 12),
            "_read_docker": (1, 2),
            "_read_zfs": ("ONLINE", 41),
        }
        probes = {name: Mock(return_value=value) for name, value in values.items()}
        for name, probe in probes.items():
            monkeypatch.setattr(collector, name, probe)
        snapshot = collector._sample()
        assert snapshot.cpu_percent == 25 and snapshot.zfs_capacity_percent == 41
        clock[0] = 1
        collector._sample()
        assert all(probe.call_count == 1 for probe in probes.values())
        clock[0] = 2
        collector._sample()
        assert probes["_read_cpu_percent"].call_count == 2
        assert probes["_read_docker"].call_count == probes["_read_zfs"].call_count == 1
        clock[0] = 10
        collector._sample()
        assert probes["_read_docker"].call_count == 2
        assert probes["_read_zfs"].call_count == 1
        clock[0] = 60
        collector._sample()
        assert probes["_read_zfs"].call_count == 2


def test_collect_returns_without_waiting_and_allows_only_one_sample(monkeypatch):
    started, release = Event(), Event()
    monkeypatch.setattr(sysinfo_module.time, "monotonic", lambda: 100.0)

    def sample():
        started.set()
        assert release.wait(1), "test release deadline exceeded"
        return SystemStats(cpu_percent=25)

    with SysInfoCollector() as collector:
        probe = Mock(side_effect=sample)
        monkeypatch.setattr(collector, "_sample", probe)
        try:
            assert collector.collect() == SystemStats()
            assert started.wait(1)
            for _ in range(5):
                assert collector.collect() == SystemStats()
            assert probe.call_count == 1
            pending = collector._pending
            release.set()
            pending.result(timeout=1)
            assert collector.collect().cpu_percent == 25
            assert probe.call_count == 1
        finally:
            release.set()
    assert collector._closed
    assert all(not thread.is_alive() for thread in collector._executor._threads)
    assert collector.collect().cpu_percent == 25


def test_failed_background_sample_keeps_last_snapshot():
    with SysInfoCollector() as collector:
        collector._snapshot = SystemStats(cpu_percent=25)
        collector._next_refresh = float("inf")
        collector._pending = Future()
        collector._pending.set_exception(OSError("unavailable"))
        assert collector.collect().cpu_percent == 25


def test_nvml_is_loaded_only_on_demand_and_closed_once(monkeypatch):
    nvml = Mock()
    nvml.nvmlDeviceGetTemperature.return_value = 45
    nvml.nvmlDeviceGetUtilizationRates.return_value = SimpleNamespace(gpu=12)
    load = Mock(return_value=nvml)
    monkeypatch.setattr(sysinfo_module, "import_module", load)
    collector = SysInfoCollector()
    load.assert_not_called()
    with collector:
        assert collector._read_gpu() == (45, 12)
        assert collector._read_gpu() == (45, 12)
    collector.shutdown()
    load.assert_called_once_with("pynvml")
    nvml.nvmlInit.assert_called_once()
    nvml.nvmlShutdown.assert_called_once()


def test_missing_nvml_is_omitted(monkeypatch):
    monkeypatch.setattr(sysinfo_module, "import_module", Mock(side_effect=ImportError))
    with SysInfoCollector() as collector:
        assert collector._read_gpu() == (None, None)


def test_nvml_handle_failure_still_releases_initialized_library(monkeypatch):
    nvml = Mock()
    nvml.nvmlDeviceGetHandleByIndex.side_effect = RuntimeError("no device")
    monkeypatch.setattr(sysinfo_module, "import_module", lambda name: nvml)
    with SysInfoCollector() as collector:
        assert collector._read_gpu() == (None, None)
    nvml.nvmlShutdown.assert_called_once()


@pytest.mark.parametrize("interval", [0, -1, float("nan"), float("inf")])
def test_invalid_sampling_intervals_are_rejected(interval):
    with pytest.raises(ValueError, match="intervals"):
        SysInfoCollector(fast_interval=interval)


@pytest.mark.parametrize("exit_mode", ["normal", "picker", "error"])
def test_runner_closes_collector_on_every_exit(monkeypatch, exit_mode):
    collector = SysInfoCollector()
    monkeypatch.setattr(collector, "_sample", lambda: SystemStats(cpu_percent=25))
    shutdown = Mock(wraps=collector.shutdown)
    monkeypatch.setattr(collector, "shutdown", shutdown)
    monkeypatch.setattr(runner_module, "SysInfoCollector", lambda **kwargs: collector)
    monkeypatch.setattr(runner_module, "keep_awake", lambda enabled: nullcontext())
    monkeypatch.setattr(runner_module, "cbreak_stdin", lambda: nullcontext(None))
    monkeypatch.setattr(runner_module, "read_key", lambda fd: None)
    monkeypatch.setattr(runner_module, "Live", MagicMock())
    runner = Runner([PlasmaScene.name], duration=0, sysinfo=True, show_picker=exit_mode == "picker")
    monkeypatch.setattr(runner, "_install_handlers", lambda: None)
    if exit_mode == "picker":
        monkeypatch.setattr(runner_module.Picker, "run", lambda *args: QUIT)
    if exit_mode == "error":
        monkeypatch.setattr(runner, "_build_scene", Mock(side_effect=RuntimeError("scene failed")))
        with pytest.raises(RuntimeError, match="scene failed"):
            runner.run()
    else:
        assert runner.run() == 0
    shutdown.assert_called_once()
    assert collector._closed
    assert all(not thread.is_alive() for thread in collector._executor._threads)


@pytest.mark.parametrize(
    "args,valid",
    [
        (["--sysinfo", "--zfs-pool", "tank"], True),
        (["--zfs-pool", "tank"], False),
        (["--sysinfo", "--zfs-pool=-a"], False),
    ],
)
def test_cli_validates_and_forwards_selected_pool(monkeypatch, args, valid):
    factory = Mock()
    factory.return_value.run.return_value = 0
    monkeypatch.setattr(cli_module, "Runner", factory)
    result = CliRunner().invoke(cli_module.main, ["java", "--no-splash", *args])
    if valid:
        assert result.exit_code == 0, result.output
        assert factory.call_args.kwargs["sysinfo"] is True
        assert factory.call_args.kwargs["zfs_pool"] == "tank"
    else:
        assert result.exit_code == 2, result.output
        factory.assert_not_called()


def test_cli_without_stats_keeps_collection_disabled(monkeypatch):
    factory = Mock()
    factory.return_value.run.return_value = 0
    monkeypatch.setattr(cli_module, "Runner", factory)
    result = CliRunner().invoke(cli_module.main, ["java", "--no-splash"])
    assert result.exit_code == 0, result.output
    assert factory.call_args.kwargs["sysinfo"] is False
    assert factory.call_args.kwargs["zfs_pool"] is None


@pytest.mark.parametrize(
    "reader", ["_read_uptime", "_read_cpu_percent", "_read_ram", "_read_cpu_temp"]
)
def test_missing_linux_sources_are_omitted(monkeypatch, reader):
    monkeypatch.setattr(Path, "read_text", Mock(side_effect=OSError))
    monkeypatch.setattr(Path, "exists", Mock(side_effect=OSError))
    with SysInfoCollector() as collector:
        assert getattr(collector, reader)() is None


@pytest.mark.parametrize("text,expected", [("183600.1 22", 183600.1), ("bad", None), ("", None)])
def test_uptime_readings(monkeypatch, text, expected):
    monkeypatch.setattr(Path, "read_text", lambda path: text)
    with SysInfoCollector() as collector:
        assert collector._read_uptime() == expected


def test_hwmon_temperature_from_fixture(monkeypatch, tmp_path):
    device = tmp_path / "hwmon0"
    device.mkdir()
    (device / "name").write_text("coretemp\n")
    (device / "temp1_input").write_text("52000\n")
    monkeypatch.setattr(sysinfo_module, "Path", lambda path: tmp_path)
    with SysInfoCollector() as collector:
        assert collector._read_cpu_temp() == 52.0


def test_complete_stats_format_and_empty_snapshot():
    stats = SystemStats(
        uptime_seconds=183600,
        cpu_percent=25,
        cpu_temp_c=52,
        ram_percent=38,
        gpu_temp_c=45,
        gpu_load_percent=12,
        docker_running=1,
        docker_total=2,
        zfs_pool_state="ONLINE",
        zfs_capacity_percent=41,
    )
    with SysInfoCollector() as collector:
        assert collector.format_footer(SystemStats()) == ""
        assert collector.format_footer(stats) == (
            "\u25b2 2d 3h \u2502 CPU 25% 52\u00b0C \u2502 GPU 12% 45\u00b0C"
            " \u2502 RAM 38% \u2502 \U0001f433 1/2 \u2502 ZFS 41% OK"
        )
