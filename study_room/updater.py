"""Self-update utilities: version check, cache, and update execution."""

import json
import subprocess
import urllib.request
from datetime import datetime, timezone, timedelta
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path

from packaging.version import Version

PYPI_PACKAGE = "ucsd-study-room"
_PACKAGE_NAMES = ["ucsd-study-room", "study-room"]
PYPI_URL = f"https://pypi.org/pypi/{PYPI_PACKAGE}/json"
CACHE_PATH = Path.home() / ".study-room" / "update_check.json"
CACHE_VERSION = 1
CHECK_INTERVAL = timedelta(days=1)


def get_current_version() -> str:
    for name in _PACKAGE_NAMES:
        try:
            return version(name)
        except PackageNotFoundError:
            continue
    return "0.0.0"


def check_pypi_latest() -> str | None:
    try:
        req = urllib.request.Request(PYPI_URL, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=1) as resp:
            data = json.loads(resp.read())
            return data["info"]["version"]
    except Exception:
        return None


def is_update_available(current: str, latest: str) -> bool:
    return Version(latest) > Version(current)


def write_cache(latest_version: str, path: Path = CACHE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cache_version": CACHE_VERSION,
        "last_check": datetime.now(timezone.utc).isoformat(),
        "latest_version": latest_version,
    }
    path.write_text(json.dumps(data))


def read_cache(path: Path = CACHE_PATH) -> dict | None:
    try:
        data = json.loads(path.read_text())
        if data.get("cache_version") != CACHE_VERSION:
            return None
        last_check = datetime.fromisoformat(data["last_check"])
        if datetime.now(timezone.utc) - last_check > CHECK_INTERVAL:
            return None
        return data
    except (FileNotFoundError, json.JSONDecodeError, KeyError, ValueError):
        return None


def get_update_notice(cache_path: Path = CACHE_PATH) -> str | None:
    current = get_current_version()
    cached = read_cache(cache_path)
    if cached:
        latest = cached["latest_version"]
    else:
        latest = check_pypi_latest()
        if latest is None:
            return None
        write_cache(latest, cache_path)

    if is_update_available(current, latest):
        return f"New version available: {current} -> {latest}\n  Run: study-room update"
    return None


def run_update() -> tuple[str, str]:
    current = get_current_version()
    latest = check_pypi_latest()
    if latest is None:
        return ("error", "Could not reach PyPI. Check your internet connection.")

    if not is_update_available(current, latest):
        return ("current", f"Already up to date ({current})")

    try:
        result = subprocess.run(
            ["uv", "tool", "install", "--upgrade", PYPI_PACKAGE],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            return ("updated", f"ucsd-study-room {latest} installed")
        else:
            return ("error", f"Update failed:\n  {result.stderr.strip()}")
    except FileNotFoundError:
        return ("error", f"uv not found. Run manually:\n  pip install --upgrade {PYPI_PACKAGE}")
    except subprocess.TimeoutExpired:
        return ("error", f"Update timed out. Run manually:\n  uv tool install --upgrade {PYPI_PACKAGE}")
