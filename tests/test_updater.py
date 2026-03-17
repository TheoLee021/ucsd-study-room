import json
import subprocess
from unittest.mock import patch, MagicMock

from study_room.updater import (
    get_current_version,
    is_update_available,
    read_cache,
    write_cache,
    get_update_notice,
    run_update,
    CACHE_VERSION,
)


# --- version utilities ---

def test_get_current_version_returns_string():
    version = get_current_version()
    assert isinstance(version, str)
    assert len(version.split(".")) >= 2


def test_is_update_available_newer():
    assert is_update_available("0.3.0", "0.4.0") is True


def test_is_update_available_same():
    assert is_update_available("0.3.0", "0.3.0") is False


def test_is_update_available_older():
    assert is_update_available("0.4.0", "0.3.0") is False


# --- cache ---

def test_write_and_read_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    write_cache("0.4.0", cache_path)
    result = read_cache(cache_path)
    assert result is not None
    assert result["latest_version"] == "0.4.0"
    assert result["cache_version"] == CACHE_VERSION


def test_read_cache_returns_none_if_missing(tmp_path):
    cache_path = tmp_path / "nonexistent.json"
    assert read_cache(cache_path) is None


def test_read_cache_returns_none_if_corrupt(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text("not json{{{")
    assert read_cache(cache_path) is None


def test_read_cache_returns_none_if_wrong_version(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({
        "cache_version": 999, "last_check": "", "latest_version": "1.0.0"
    }))
    assert read_cache(cache_path) is None


def test_read_cache_returns_none_if_expired(tmp_path):
    cache_path = tmp_path / "cache.json"
    old_time = "2020-01-01T00:00:00+00:00"
    cache_path.write_text(json.dumps({
        "cache_version": CACHE_VERSION, "last_check": old_time, "latest_version": "1.0.0"
    }))
    assert read_cache(cache_path) is None


def test_read_cache_returns_none_if_missing_keys(tmp_path):
    cache_path = tmp_path / "cache.json"
    cache_path.write_text(json.dumps({"cache_version": CACHE_VERSION}))
    assert read_cache(cache_path) is None


# --- get_update_notice ---

def test_get_update_notice_returns_none_when_current(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.3.0"):
        notice = get_update_notice(cache_path)
    assert notice is None


def test_get_update_notice_returns_message_when_outdated(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0"):
        notice = get_update_notice(cache_path)
    assert "0.3.0" in notice
    assert "0.4.0" in notice


def test_get_update_notice_returns_none_when_pypi_unreachable(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value=None):
        notice = get_update_notice(cache_path)
    assert notice is None


def test_get_update_notice_uses_cache(tmp_path):
    cache_path = tmp_path / "cache.json"
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0") as mock_pypi:
        get_update_notice(cache_path)
        get_update_notice(cache_path)
    assert mock_pypi.call_count == 1


# --- run_update ---

def test_run_update_already_current():
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.3.0"):
        status, message = run_update()
    assert status == "current"
    assert "up to date" in message.lower()


def test_run_update_pypi_unreachable():
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value=None):
        status, message = run_update()
    assert status == "error"
    assert "PyPI" in message


def test_run_update_success():
    mock_result = MagicMock(returncode=0)
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0"), \
         patch("subprocess.run", return_value=mock_result):
        status, message = run_update()
    assert status == "updated"
    assert "0.4.0" in message


def test_run_update_subprocess_fails():
    mock_result = MagicMock(returncode=1, stderr="some error")
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0"), \
         patch("subprocess.run", return_value=mock_result):
        status, message = run_update()
    assert status == "error"
    assert "failed" in message.lower()


def test_run_update_uv_not_found():
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0"), \
         patch("subprocess.run", side_effect=FileNotFoundError):
        status, message = run_update()
    assert status == "error"
    assert "uv not found" in message


def test_run_update_timeout():
    with patch("study_room.updater.get_current_version", return_value="0.3.0"), \
         patch("study_room.updater.check_pypi_latest", return_value="0.4.0"), \
         patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="uv", timeout=120)):
        status, message = run_update()
    assert status == "error"
    assert "timed out" in message.lower()
