"""Cerber Security simulated root helper.

This module mirrors the lightweight playground that was described in the
original concept: a couple of background "guardian" processes mapped to
Chinese alphabet symbols that continuously write diagnostic messages into a
fake root directory.  The goal of this rewrite is to keep that behaviour while
adding a reliable way to choose and consolidate the canonical fake root path.

The module can be executed as a script.  By default it prefers the
``/data/local/tmp/guardian_sim`` folder (common on Android test devices) and
falls back to ``./guardian_sim`` when the former is not writable.  Duplicate
folders are merged safely so that only one canonical location remains.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import random
import shutil
import threading
import time
from pathlib import Path
from typing import Dict, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_ROOT = Path("/data/local/tmp/guardian_sim")
FALLBACK_ROOT = Path.cwd() / "guardian_sim"


# ---------------------------------------------------------------------------
# Fake root directory helpers
# ---------------------------------------------------------------------------


def _can_write(path: Path) -> bool:
    """Return ``True`` when *path* exists (or can be created) and is writable."""

    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".cerber_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        return True
    except Exception:
        return False


def _unique_name(path: Path, suffix: str = ".dup") -> Path:
    """Return a path under the same parent that does not clash with *path*.

    ``suffix`` is appended together with an incrementing number whenever a
    collision occurs (``file.log`` → ``file.log.dup1`` → ``file.log.dup2`` ...).
    """

    candidate = path
    counter = 1
    while candidate.exists():
        candidate = path.with_name(f"{path.name}{suffix}{counter}")
        counter += 1
    return candidate


def _safe_move(src: Path, dst_dir: Path) -> None:
    """Move *src* into *dst_dir* without clobbering existing files."""

    destination = dst_dir / src.name
    if destination.exists():
        destination = _unique_name(destination)
    shutil.move(str(src), str(destination))


def _log_consolidation_message(target: Path, filename: str, message: str) -> None:
    """Persist best-effort logs about consolidation issues."""

    try:
        target.mkdir(parents=True, exist_ok=True)
        log_path = target / filename
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        with open(log_path, "a", encoding="utf-8") as handle:
            handle.write(f"[{timestamp}] {message}\n")
    except Exception:
        # Logging must never explode consolidation.
        pass


def consolidate_dirs(chosen: Path, other: Path) -> None:
    """Merge contents of *other* into *chosen* while keeping data safe."""

    if not other.exists():
        return

    chosen.mkdir(parents=True, exist_ok=True)

    for item in other.iterdir():
        try:
            _safe_move(item, chosen)
        except Exception as exc:  # pragma: no cover - best effort logging
            _log_consolidation_message(
                chosen,
                "consolidation_errors.log",
                f"Error moving {item} into {chosen}: {exc}",
            )

    try:
        other.rmdir()
    except OSError:
        _log_consolidation_message(
            chosen,
            "consolidation_warnings.log",
            f"Could not remove {other} – directory not empty or permission denied",
        )


def choose_and_consolidate_root(
    default: Path,
    fallback: Path,
    *,
    env_var: Optional[str] = "CERBER_SIMROOT_PATH",
    force_root: Optional[Path] = None,
    merge_existing: bool = True,
) -> Path:
    """Pick the canonical fake root directory and consolidate other folders."""

    def _merge_into(target: Path) -> None:
        if not merge_existing:
            return

        for candidate in (default, fallback):
            if not candidate.exists():
                continue
            try:
                if candidate.resolve() == target.resolve():
                    continue
            except OSError:
                # ``resolve`` can fail when the user lacks permissions – just skip.
                continue
            consolidate_dirs(target, candidate)

    if force_root is not None:
        chosen = force_root.expanduser()
        chosen.mkdir(parents=True, exist_ok=True)
        _merge_into(chosen)
        return chosen

    if env_var:
        env_override = os.environ.get(env_var)
        if env_override:
            chosen = Path(env_override).expanduser()
            chosen.mkdir(parents=True, exist_ok=True)
            _merge_into(chosen)
            return chosen

    if _can_write(default):
        chosen = default
        _merge_into(chosen)
        return chosen

    if _can_write(fallback):
        chosen = fallback
        _merge_into(chosen)
        return chosen

    # Final fallback: create a folder relative to the current working directory.
    alternative = Path.cwd() / "guardian_sim"
    alternative.mkdir(parents=True, exist_ok=True)
    return alternative


# Canonical fake root directory used by all logging helpers.
ROOT_PATH = choose_and_consolidate_root(DEFAULT_ROOT, FALLBACK_ROOT)


# ---------------------------------------------------------------------------
# Logging helper
# ---------------------------------------------------------------------------


def log(process: str, message: str) -> None:
    """Write a simulated root-level log entry for *process*."""

    log_path = ROOT_PATH / f"{process}.log"
    with open(log_path, "a", encoding="utf-8") as handle:
        handle.write(f"[{time.strftime('%H:%M:%S')}] {message}\n")


# ---------------------------------------------------------------------------
# Cerber process implementations
# ---------------------------------------------------------------------------


def system_monitor() -> None:
    while True:
        log("system_monitor", "扫描系统内核 (Kernel scan) ... OK")
        time.sleep(3)


def guardian_watchdog() -> None:
    while True:
        fake_hash = hashlib.sha256(os.urandom(16)).hexdigest()[:16]
        log("guardian_watchdog", f"守护线程运行中 (Guardian active) – token={fake_hash}")
        time.sleep(5)


def memory_scan() -> None:
    while True:
        usage = random.randint(40, 92)
        log("memory_scan", f"内存检查: 使用率 {usage}%")
        time.sleep(4)


def purge_emulator() -> None:
    while True:
        log("purge_emulator", "模拟清理缓存... 完成 (Wipe simulation complete)")
        time.sleep(10)


def network_trace() -> None:
    while True:
        packets = random.randint(10, 70)
        log("network_trace", f"网络流量监控: {packets} 包捕获 (packets)")
        time.sleep(6)


def integrity_check() -> None:
    while True:
        checksum = hashlib.md5(os.urandom(32)).hexdigest()
        log("integrity_check", f"完整性验证 (Integrity check) – md5={checksum}")
        time.sleep(8)


CERBER_PROCESSES: Dict[str, str] = {
    "甲": "system_monitor",
    "乙": "guardian_watchdog",
    "丙": "memory_scan",
    "丁": "purge_emulator",
    "戊": "network_trace",
    "己": "integrity_check",
}


# ---------------------------------------------------------------------------
# Thread orchestration
# ---------------------------------------------------------------------------


def start_process(symbol: str) -> None:
    """Start the Cerber process mapped to *symbol* in a daemon thread."""

    if symbol not in CERBER_PROCESSES:
        print(f"⚠️ Nieznany symbol: {symbol}")
        return

    func_name = CERBER_PROCESSES[symbol]
    func = globals()[func_name]
    thread = threading.Thread(target=func, name=f"cerber-{func_name}", daemon=True)
    thread.start()
    print(f"✅ [{symbol}] Proces {func_name} uruchomiony (SimRoot mode)")


def auto_start_all() -> None:
    for symbol in CERBER_PROCESSES:
        start_process(symbol)


# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Cerber SimRoot – lightweight guardian process simulator",
    )
    parser.add_argument(
        "--force-root",
        type=Path,
        help="Force the canonical fake root directory to the given path",
    )
    merge_group = parser.add_mutually_exclusive_group()
    merge_group.add_argument(
        "--merge-existing",
        dest="merge_existing",
        action="store_true",
        help="Merge any secondary fake root directories into the canonical one",
    )
    merge_group.add_argument(
        "--no-merge-existing",
        dest="merge_existing",
        action="store_false",
        help="Skip consolidation of existing fake root directories",
    )
    parser.set_defaults(merge_existing=None)
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    merge_existing = True if args.merge_existing is None else args.merge_existing

    global ROOT_PATH
    ROOT_PATH = choose_and_consolidate_root(
        DEFAULT_ROOT,
        FALLBACK_ROOT,
        force_root=args.force_root,
        merge_existing=merge_existing,
    )

    print("🐉 Cerber SimRoot aktywny. Procesy kontrolowane alfabetem chińskim:")
    for symbol, name in CERBER_PROCESSES.items():
        print(f" {symbol} → {name}")

    auto_start_all()

    print(f"\n📂 Fake root folder: {ROOT_PATH}")
    print("🔍 Logi aktualizują się co kilka sekund... (Ctrl+C aby zakończyć)\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Zatrzymywanie symulacji...")


if __name__ == "__main__":
    main()
