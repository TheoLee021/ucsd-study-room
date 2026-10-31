import asyncio
import json
import os
from datetime import datetime, timedelta
from pathlib import Path

import keyring
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright
from rich.console import Console

SESSION_DIR = Path.home() / ".study-room"
SESSION_PATH = SESSION_DIR / "session.json"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"
SESSION_MAX_AGE_DAYS = 7
EMS_URL = "https://ucsdevents.emscloudservice.com/web/"
SAML_URL = "https://ucsdevents.emscloudservice.com/web/samlauth.aspx"
LOGIN_TIMEOUT_S = 90
UNKNOWN_PAGE_TIMEOUT_S = 20
DEBUG_DIR = SESSION_DIR / "debug"
KEYRING_SERVICE = "study-room-booking"
KEYRING_USERNAME_KEY = "ucsd-sso-username"


# stderr: stdout is the MCP stdio protocol channel.
# The CLI shares this console for its spinner.
console = Console(stderr=True, highlight=False)
DUO_REMINDER_EVERY_S = 15


def _log(*args) -> None:
    console.print(*args, markup=False)


def _headless() -> bool:
    return os.environ.get("STUDY_ROOM_HEADED") != "1"


def _write_private(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)


def save_credentials(username: str, password: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, username)
        keyring.set_password(KEYRING_SERVICE, username, password)
    except Exception:
        _log(
            "Warning: Could not save credentials to system keyring. "
            "Credentials will not be remembered for auto-login."
        )


def load_credentials() -> tuple[str, str] | None:
    try:
        username = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
        if username is None:
            return None
        password = keyring.get_password(KEYRING_SERVICE, username)
        if password is None:
            return None
        return username, password
    except Exception:
        return None


def save_session(cookies: list, path: Path = SESSION_PATH) -> None:
    data = {
        "cookies": cookies,
        "created_at": datetime.now().isoformat(),
    }
    _write_private(path, json.dumps(data, indent=2))


def load_session(path: Path = SESSION_PATH) -> dict | None:
    if not path.exists():
        return None
    return json.loads(path.read_text())


def is_session_valid(path: Path = SESSION_PATH) -> bool:
    session = load_session(path)
    if session is None:
        return False
    created = datetime.fromisoformat(session["created_at"])
    return datetime.now() - created < timedelta(days=SESSION_MAX_AGE_DAYS)


class SessionExpiredError(Exception):
    pass


class LoginError(SessionExpiredError):
    pass


def _on_ems(url: str) -> bool:
    return "emscloudservice.com/web/" in url and "samlauth" not in url


def classify_page(url: str, html: str) -> str:
    """Login state of the current page.

    One of: ems | duo_trust | duo | sso_error | sso_form | unknown.
    """
    if _on_ems(url):
        return "ems"
    if "duosecurity.com" in url:
        return "duo_trust" if "Is this your device?" in html else "duo"
    if 'id="_login_error_message"' in html:
        return "sso_error"
    if 'id="ssousername"' in html:
        return "sso_form"
    return "unknown"


async def _dump_debug(page) -> Path | None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = DEBUG_DIR / f"login-{stamp}"
    try:
        _write_private(base.with_suffix(".html"), await page.content())
        await page.screenshot(path=str(base.with_suffix(".png")), full_page=True)
        base.with_suffix(".png").chmod(0o600)
        return base
    except Exception:
        return None


async def _fail(page, message: str):
    base = await _dump_debug(page)
    if base:
        message += f" Debug files: {base}.png/.html"
    raise LoginError(message)


_STATE_MESSAGES = {
    "duo": "Waiting for Duo — approve the push on your phone if prompted...",
    "duo_trust": "Duo approved. Remembering this browser...",
    "ems": "Finishing login...",
}


async def _sso_login(page, username: str, password: str) -> None:
    """Fill the UCSD SSO form, then wait for Duo Push approval and the EMS redirect.

    Duo sends the push automatically. Clicks "Yes, this is my device" on the trust
    prompt, which also lets Duo remember this browser for later logins.
    """
    _log("Submitting credentials...")
    await page.locator("#ssousername").fill(username)
    await page.locator("#ssopassword").fill(password)
    await page.locator("button[type='submit']").click()

    loop = asyncio.get_running_loop()
    start = loop.time()
    unknown_since = None
    state = None
    next_reminder = None
    announced = set()
    trust_clicked = False
    while loop.time() - start < LOGIN_TIMEOUT_S:
        await asyncio.sleep(0.5)
        try:
            state = classify_page(page.url, await page.content())
            if state in _STATE_MESSAGES and state not in announced:
                _log(_STATE_MESSAGES[state])
                announced.add(state)
            if state == "duo" and "duo_trust" not in announced:
                if next_reminder is None:
                    next_reminder = loop.time() + DUO_REMINDER_EVERY_S
                elif loop.time() >= next_reminder:
                    waited = int(loop.time() - start)
                    _log(f"Still waiting for Duo... ({waited}s / {LOGIN_TIMEOUT_S}s)")
                    next_reminder += DUO_REMINDER_EVERY_S
            if state == "ems":
                await page.wait_for_load_state("networkidle")
                return
            if state == "duo_trust" and not trust_clicked:
                trust_button = page.get_by_role("button", name="Yes, this is my device")
                await trust_button.click(timeout=5000)
                trust_clicked = True
            elif state == "sso_error":
                # Report the SSO server's own message (wrong password, locked account...)
                error_box = page.locator("#_login_error_message")
                reason = (await error_box.inner_text()).strip()
                raise LoginError(f"SSO login failed: {reason}")
        except PlaywrightError:
            continue  # page navigating mid-check

        if state in ("sso_form", "unknown"):
            unknown_since = unknown_since or loop.time()
            if loop.time() - unknown_since > UNKNOWN_PAGE_TIMEOUT_S:
                where = "SSO page" if state == "sso_form" else "an unexpected page"
                await _fail(page, f"Login stuck on {where} ({page.url}).")
        else:
            unknown_since = None

    if state in ("duo", "duo_trust"):
        await _fail(page, "Timed out waiting for Duo approval.")
    await _fail(page, f"Login timed out on an unexpected page ({page.url}).")


async def _save_storage(context, session_path: Path) -> list:
    cookies = await context.cookies()
    save_session(cookies, session_path)
    storage_state_path = session_path.parent / "storage_state.json"
    await context.storage_state(path=str(storage_state_path))
    storage_state_path.chmod(0o600)
    return cookies


def _duo_trust_state(session_path: Path) -> dict | None:
    """Only the Duo cookies/storage from the saved state, or None if there is none."""
    path = session_path.parent / "storage_state.json"
    if not path.exists():
        return None
    state = json.loads(path.read_text())
    return {
        "cookies": [
            c for c in state.get("cookies", []) if "duosecurity.com" in c["domain"]
        ],
        "origins": [
            o for o in state.get("origins", []) if "duosecurity.com" in o["origin"]
        ],
    }


async def login(
    username: str,
    password: str,
    session_path: Path = SESSION_PATH,
    headless: bool | None = None,
) -> list:
    """Headless SSO login + Duo Push. Saves credentials and cookies on success."""
    if headless is None:
        headless = _headless()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=headless, channel="chrome")
        # Fresh SSO session (user may switch accounts),
        # but keep Duo's "remember this browser" cookie
        trust_state = _duo_trust_state(session_path)
        context = await browser.new_context(storage_state=trust_state)
        page = await context.new_page()

        _log("Opening UCSD SSO login page...")
        await page.goto(SAML_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_selector("#ssousername", timeout=15000)
        await _sso_login(page, username, password)

        save_credentials(username, password)
        cookies = await _save_storage(context, session_path)
        _log(f"Login successful! {len(cookies)} cookies + storage state saved.")

        await browser.close()
        return cookies


async def get_authenticated_context(
    playwright,
    session_path: Path = SESSION_PATH,
    headless: bool | None = None,
    channel: str | None = "chrome",
):
    """Return a browser context with saved storage state.

    If the session is stale but keychain credentials exist, still loads the saved state
    (it carries the Duo trust cookie) and lets authenticate() log in headlessly.
    Returns None if neither a valid session nor credentials are available.
    """
    session_valid = is_session_valid(session_path)
    if not session_valid and load_credentials() is None:
        return None

    storage_state_path = session_path.parent / "storage_state.json"
    launch_args = {"headless": _headless() if headless is None else headless}
    if channel:
        launch_args["channel"] = channel
    browser = await playwright.chromium.launch(**launch_args)

    if storage_state_path.exists():
        context = await browser.new_context(storage_state=str(storage_state_path))
    elif not session_valid:
        context = await browser.new_context()
    else:
        session = load_session(session_path)
        context = await browser.new_context()
        await context.add_cookies(session["cookies"])

    return context


async def authenticate(page, session_path: Path = SESSION_PATH) -> None:
    """SAML authentication.

    Auto-passes if SSO is valid, otherwise logs in headlessly from keychain.
    """
    _log("Authenticating via SAML...")

    await page.goto(SAML_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    if await page.locator("#ssousername").count() > 0:
        creds = load_credentials()
        if creds is None:
            raise SessionExpiredError(
                "SSO session expired. Please run 'study-room login'."
            )
        _log("SSO session expired. Logging in with saved credentials...")
        await _sso_login(page, *creds)
    else:
        # SSO valid → auto-redirects to EMS
        await page.wait_for_url("**/web/**", timeout=15000)

    await _save_storage(page.context, session_path)
    _log("Authentication complete.")
