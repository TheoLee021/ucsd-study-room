import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

from study_room.auth import classify_page, is_session_valid, load_session, save_session

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


# --- classify_page ---

DUO_URL = "https://api-ce13a1a7.duosecurity.com/prompt/XYZ?authkey=ABC"


EMS_URL = "https://ucsdevents.emscloudservice.com/web/Default.aspx"
SAML_URL = "https://ucsdevents.emscloudservice.com/web/samlauth.aspx"
SSO_URL = "https://a5.ucsd.edu/tritON/profile/SAML2/Redirect/SSO?execution=e1s2"


def test_classify_ems():
    assert classify_page(EMS_URL, "") == "ems"


def test_classify_saml_page_is_not_ems():
    assert classify_page(SAML_URL, "") == "unknown"


def test_classify_duo_push():
    assert classify_page(DUO_URL, "<h1>Check for a Duo Push</h1>") == "duo"


def test_classify_duo_trust():
    assert classify_page(DUO_URL, "<h1>Is this your device?</h1>") == "duo_trust"


def test_classify_sso_form():
    html = '<input id="ssousername" name="j_username">'
    assert classify_page(SSO_URL, html) == "sso_form"


def test_classify_sso_error():
    html = (
        '<div id="_login_error_message" class="alert alert-warning">'
        "The password you entered was incorrect.</div>"
        '<input id="ssousername" name="j_username">'
    )
    assert classify_page(SSO_URL, html) == "sso_error"


def test_classify_unknown():
    assert classify_page("https://a5.ucsd.edu/other", "<p>hi</p>") == "unknown"


# --- file permissions ---


def test_save_session_is_owner_only(tmp_path):
    session_path = tmp_path / "session.json"
    save_session(SAMPLE_COOKIES, session_path)
    assert session_path.stat().st_mode & 0o777 == 0o600


def test_save_storage_files_are_owner_only(tmp_path):
    from study_room.auth import _save_storage

    class FakeContext:
        async def cookies(self):
            return SAMPLE_COOKIES

        async def storage_state(self, path):
            Path(path).write_text("{}")

    session_path = tmp_path / "session.json"
    asyncio.run(_save_storage(FakeContext(), session_path))
    assert session_path.stat().st_mode & 0o777 == 0o600
    assert (tmp_path / "storage_state.json").stat().st_mode & 0o777 == 0o600


def test_debug_dump_files_are_owner_only(tmp_path, monkeypatch):
    from study_room import auth

    class FakePage:
        async def content(self):
            return "<html></html>"

        async def screenshot(self, path, full_page):
            Path(path).write_bytes(b"png")

    monkeypatch.setattr(auth, "DEBUG_DIR", tmp_path / "debug")
    base = asyncio.run(auth._dump_debug(FakePage()))
    assert base.with_suffix(".html").stat().st_mode & 0o777 == 0o600
    assert base.with_suffix(".png").stat().st_mode & 0o777 == 0o600


def test_duo_trust_state_keeps_only_duo(tmp_path):
    from study_room.auth import _duo_trust_state

    state = {
        "cookies": [
            {"name": "a", "domain": "api-x.duosecurity.com"},
            {"name": "b", "domain": "a5.ucsd.edu"},
        ],
        "origins": [
            {"origin": "https://api-x.duosecurity.com", "localStorage": []},
            {"origin": "https://ucsdevents.emscloudservice.com", "localStorage": []},
        ],
    }
    (tmp_path / "storage_state.json").write_text(json.dumps(state))
    trimmed = _duo_trust_state(tmp_path / "session.json")
    assert [c["name"] for c in trimmed["cookies"]] == ["a"]
    assert [o["origin"] for o in trimmed["origins"]] == ["https://api-x.duosecurity.com"]
    assert _duo_trust_state(tmp_path / "nowhere" / "session.json") is None
