"""Live system stats collector for the server kiosk footer.

Samples /proc, /sys, optional NVML, Docker and an explicitly selected ZFS pool
on one background worker. Rendering only reads completed snapshots; unavailable
sources are omitted. Docker has a socket timeout and a response-size limit,
and the ZFS command has a subprocess timeout.

Stats are cached and refreshed on a configurable interval (default 2s for
lightweight /proc reads, 60s for the ZFS subprocess).
"""

from __future__ import annotations

import http.client
import json
import math
import re
import socket
import subprocess
import time
import warnings
from concurrent.futures import Future, ThreadPoolExecutor
from contextlib import suppress
from dataclasses import dataclass
from importlib import import_module
from pathlib import Path


@dataclass
class SystemStats:
    """Snapshot of system metrics."""

    uptime_seconds: float | None = None
    cpu_percent: float | None = None
    cpu_temp_c: float | None = None
    ram_percent: float | None = None
    gpu_temp_c: int | None = None
    gpu_load_percent: int | None = None
    docker_running: int | None = None
    docker_total: int | None = None
    zfs_pool_state: str | None = None
    zfs_capacity_percent: int | None = None


@dataclass
class _CacheEntry:
    value: object = None
    updated_at: float = 0.0


class SysInfoCollector:
    """Collects and caches system stats from various sources."""

    def __init__(
        self,
        fast_interval: float = 2.0,
        zfs_interval: float = 60.0,
        docker_interval: float = 10.0,
        zfs_pool: str | None = None,
    ) -> None:
        if zfs_pool is not None and not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.:-]*", zfs_pool):
            raise ValueError("Invalid ZFS pool name")
        if not all(
            math.isfinite(value) and value > 0
            for value in (fast_interval, zfs_interval, docker_interval)
        ):
            raise ValueError("Sampling intervals must be positive and finite")
        self._zfs_pool = zfs_pool
        self._fast_interval = fast_interval
        self._zfs_interval = zfs_interval
        self._docker_interval = docker_interval
        self._cache: dict[str, _CacheEntry] = {}
        self._nvml_initialized = False
        self._nvml_started = False
        self._nvml = None
        self._nvml_handle = None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="javalamp-stats")
        self._pending: Future[SystemStats] | None = None
        self._snapshot = SystemStats()
        self._next_refresh = 0.0
        self._closed = False
        # Previous /proc/stat snapshot for CPU % delta calculation.
        self._prev_cpu_times: tuple[int, int] | None = None  # (idle, total)

    def _is_stale(self, key: str, max_age: float) -> bool:
        entry = self._cache.get(key)
        if entry is None:
            return True
        return (time.monotonic() - entry.updated_at) >= max_age

    def _store(self, key: str, value: object) -> None:
        if key not in self._cache:
            self._cache[key] = _CacheEntry()
        self._cache[key].value = value
        self._cache[key].updated_at = time.monotonic()

    def _get(self, key: str) -> object:
        entry = self._cache.get(key)
        return entry.value if entry else None

    # -- /proc readers --------------------------------------------------------

    def _read_uptime(self) -> float | None:
        try:
            text = Path("/proc/uptime").read_text()
            return float(text.split()[0])
        except (OSError, ValueError, IndexError):
            return None

    def _read_cpu_percent(self) -> float | None:
        """Calculate CPU usage % from /proc/stat delta between samples."""
        try:
            text = Path("/proc/stat").read_text()
            # First line: cpu <user> <nice> <system> <idle> <iowait> ...
            first_line = text.split("\n", 1)[0]
            parts = first_line.split()
            if parts[0] != "cpu":
                return None
            times = [int(value) for value in parts[1:9]]
            idle = times[3] + (times[4] if len(times) > 4 else 0)  # idle + iowait
            total = sum(times)

            if self._prev_cpu_times is None:
                self._prev_cpu_times = (idle, total)
                return None

            prev_idle, prev_total = self._prev_cpu_times
            self._prev_cpu_times = (idle, total)

            d_idle = idle - prev_idle
            d_total = total - prev_total
            if d_total < 0 or d_idle < 0:
                return None
            if d_total == 0:
                return 0.0
            return max(0.0, min(100.0, ((d_total - d_idle) / d_total) * 100.0))
        except (OSError, ValueError, IndexError):
            return None

    def _read_cpu_temp(self) -> float | None:
        """Read CPU temp from hwmon. Searches for coretemp or k10temp."""
        try:
            hwmon_base = Path("/sys/class/hwmon")
            if not hwmon_base.exists():
                return None
            for hwmon_dir in hwmon_base.iterdir():
                name_file = hwmon_dir / "name"
                if not name_file.exists():
                    continue
                name = name_file.read_text().strip()
                if name in ("coretemp", "k10temp", "zenpower"):
                    # Read the package/die temp (temp1) or first core temp
                    for label_candidate in ("temp1_input", "temp2_input"):
                        temp_file = hwmon_dir / label_candidate
                        if temp_file.exists():
                            val = int(temp_file.read_text().strip())
                            return val / 1000.0  # millidegrees -> degrees
            return None
        except (OSError, ValueError):
            return None

    def _read_ram(self) -> float | None:
        try:
            info: dict[str, int] = {}
            for line in Path("/proc/meminfo").read_text().splitlines():
                parts = line.split()
                if len(parts) >= 2:
                    key = parts[0].rstrip(":")
                    info[key] = int(parts[1])
            total = info.get("MemTotal", 0)
            available = info.get("MemAvailable")
            if total <= 0 or available is None or not 0 <= available <= total:
                return None
            return ((total - available) / total) * 100.0
        except (OSError, ValueError):
            return None

    # -- NVIDIA GPU -----------------------------------------------------------

    def _init_nvml(self) -> bool:
        if self._nvml_initialized:
            return self._nvml_handle is not None
        self._nvml_initialized = True
        try:
            with warnings.catch_warnings():
                warnings.filterwarnings("ignore", category=FutureWarning)
                self._nvml = import_module("pynvml")
            self._nvml.nvmlInit()
            self._nvml_started = True
            self._nvml_handle = self._nvml.nvmlDeviceGetHandleByIndex(0)
            return True
        except Exception:
            self._nvml_handle = None
            return False

    def _read_gpu(self) -> tuple[int | None, int | None]:
        """Returns (temp_c, utilization_percent)."""
        if not self._init_nvml():
            return None, None
        try:
            temp = self._nvml.nvmlDeviceGetTemperature(
                self._nvml_handle, self._nvml.NVML_TEMPERATURE_GPU
            )
            util = self._nvml.nvmlDeviceGetUtilizationRates(self._nvml_handle)
            return temp, util.gpu
        except Exception:
            return None, None

    # -- Docker socket --------------------------------------------------------

    def _read_docker(self) -> tuple[int | None, int | None]:
        """Query Docker daemon via Unix socket. Returns (running, total)."""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(1.0)
                sock.connect("/var/run/docker.sock")
                sock.sendall(
                    b"GET /containers/json?all=true HTTP/1.1\r\n"
                    b"Host: localhost\r\nConnection: close\r\n\r\n"
                )
                with http.client.HTTPResponse(sock) as response:
                    response.begin()
                    if response.status != 200:
                        return None, None
                    body = response.read(1024 * 1024 + 1)
            if len(body) > 1024 * 1024:
                return None, None
            containers = json.loads(body)
            if not isinstance(containers, list) or not all(
                isinstance(container, dict) for container in containers
            ):
                return None, None
            total = len(containers)
            running = sum(container.get("State") == "running" for container in containers)
            return running, total
        except (OSError, ValueError, TypeError, AttributeError, http.client.HTTPException):
            return None, None

    # -- ZFS ------------------------------------------------------------------

    def _read_zfs(self) -> tuple[str | None, int | None]:
        """Read health and capacity only for an explicitly selected pool."""
        if self._zfs_pool is None:
            return None, None
        try:
            result = subprocess.run(
                ["zpool", "list", "-Hp", "-o", "health,cap", self._zfs_pool],
                capture_output=True,
                text=True,
                stdin=subprocess.DEVNULL,
                timeout=2,
            )
            if result.returncode != 0:
                return None, None
            state, capacity = result.stdout.split()
            capacity = int(capacity.rstrip("%"))
            if not 0 <= capacity <= 100:
                return None, None
            return state.upper(), capacity
        except (OSError, ValueError, subprocess.TimeoutExpired):
            return None, None

    # -- public API -----------------------------------------------------------

    def collect(self) -> SystemStats:
        """Return the latest completed snapshot without waiting for sampling."""
        if self._closed:
            return self._snapshot
        if self._pending is not None and self._pending.done():
            with suppress(Exception):
                self._snapshot = self._pending.result()
            self._pending = None
        now = time.monotonic()
        if self._pending is None and now >= self._next_refresh:
            self._pending = self._executor.submit(self._sample)
            self._next_refresh = now + self._fast_interval
        return self._snapshot

    def _sample(self) -> SystemStats:
        """Refresh stale sources on the single sampling worker."""
        stats = SystemStats()

        # Fast stats (every 2s) — /proc and /sys file reads.
        if self._is_stale("fast", self._fast_interval):
            self._store("uptime", self._read_uptime())
            self._store("cpu_percent", self._read_cpu_percent())
            self._store("cpu_temp", self._read_cpu_temp())
            self._store("ram", self._read_ram())
            gpu_temp, gpu_load = self._read_gpu()
            self._store("gpu_temp", gpu_temp)
            self._store("gpu_load", gpu_load)
            self._store("fast", True)

        # Docker (every 10s).
        if self._is_stale("docker", self._docker_interval):
            running, total = self._read_docker()
            self._store("docker_running", running)
            self._store("docker_total", total)
            self._store("docker", True)

        if self._is_stale("zfs", self._zfs_interval):
            state, capacity = self._read_zfs()
            self._store("zfs_state", state)
            self._store("zfs_cap", capacity)
            self._store("zfs", True)

        stats.uptime_seconds = self._get("uptime")
        stats.cpu_percent = self._get("cpu_percent")
        stats.cpu_temp_c = self._get("cpu_temp")
        stats.ram_percent = self._get("ram")
        stats.gpu_temp_c = self._get("gpu_temp")
        stats.gpu_load_percent = self._get("gpu_load")
        stats.docker_running = self._get("docker_running")
        stats.docker_total = self._get("docker_total")
        stats.zfs_pool_state = self._get("zfs_state")
        stats.zfs_capacity_percent = self._get("zfs_cap")

        return stats

    def format_footer(self, stats: SystemStats) -> str:
        """Format stats into a compact single-line string."""
        parts: list[str] = []

        # Uptime.
        if stats.uptime_seconds is not None:
            days = int(stats.uptime_seconds // 86400)
            hours = int((stats.uptime_seconds % 86400) // 3600)
            if days > 0:
                parts.append(f"▲ {days}d {hours}h")
            else:
                mins = int((stats.uptime_seconds % 3600) // 60)
                parts.append(f"▲ {hours}h {mins}m")

        # CPU.
        cpu_parts: list[str] = []
        if stats.cpu_percent is not None:
            cpu_parts.append(f"{stats.cpu_percent:.0f}%")
        if stats.cpu_temp_c is not None:
            cpu_parts.append(f"{stats.cpu_temp_c:.0f}°C")
        if cpu_parts:
            parts.append(f"CPU {' '.join(cpu_parts)}")

        # GPU.
        gpu_parts: list[str] = []
        if stats.gpu_load_percent is not None:
            gpu_parts.append(f"{stats.gpu_load_percent}%")
        if stats.gpu_temp_c is not None:
            gpu_parts.append(f"{stats.gpu_temp_c}°C")
        if gpu_parts:
            parts.append(f"GPU {' '.join(gpu_parts)}")

        # RAM.
        if stats.ram_percent is not None:
            parts.append(f"RAM {stats.ram_percent:.0f}%")

        # Docker.
        if stats.docker_running is not None and stats.docker_total is not None:
            parts.append(f"🐳 {stats.docker_running}/{stats.docker_total}")

        # ZFS.
        zfs_parts: list[str] = []
        if stats.zfs_capacity_percent is not None:
            zfs_parts.append(f"{stats.zfs_capacity_percent}%")
        if stats.zfs_pool_state is not None:
            state = stats.zfs_pool_state
            # Shorten ONLINE to OK for space.
            if state == "ONLINE":
                state = "OK"
            zfs_parts.append(state)
        if zfs_parts:
            parts.append(f"ZFS {' '.join(zfs_parts)}")

        return " │ ".join(parts)

    def shutdown(self) -> None:
        """Finish any in-flight sample before releasing GPU resources."""
        if self._closed:
            return
        self._closed = True
        self._executor.shutdown(wait=True, cancel_futures=True)
        if self._nvml_started:
            with suppress(Exception):
                self._nvml.nvmlShutdown()

    def __enter__(self) -> SysInfoCollector:
        return self

    def __exit__(self, *exc: object) -> None:
        self.shutdown()
