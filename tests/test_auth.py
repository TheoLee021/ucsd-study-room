import json
from datetime import datetime, timedelta
from study_room.auth import save_session, load_session, is_session_valid

SAMPLE_COOKIES = [
    {"name": "session_id", "value": "abc123", "domain": ".emscloudservice.com"}
]


def test_save_and_load_session(tmp_path):
    session_path = tmp_path / "session.json"
    save_session(SAMPLE_COOKIES, session_path)
    loaded = load_session(session_path)
    assert loaded["cookies"] == SAMPLE_COOKIES
    assert "created_at" in loaded


def test_load_session_returns_none_if_missing(tmp_path):
    session_path = tmp_path / "session.json"
    loaded = load_session(session_path)
    assert loaded is None


def test_is_session_valid_with_fresh_session(tmp_path):
    session_path = tmp_path / "session.json"
    save_session(SAMPLE_COOKIES, session_path)
    assert is_session_valid(session_path) is True


def test_is_session_valid_with_expired_session(tmp_path):
    session_path = tmp_path / "session.json"
    expired = {
        "cookies": SAMPLE_COOKIES,
        "created_at": (datetime.now() - timedelta(days=15)).isoformat(),
    }
    session_path.write_text(json.dumps(expired))
    assert is_session_valid(session_path) is False
