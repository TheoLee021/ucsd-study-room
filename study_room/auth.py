import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path

import keyring
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import async_playwright

SESSION_DIR = Path.home() / ".study-room"
SESSION_PATH = SESSION_DIR / "session.json"
STORAGE_STATE_PATH = SESSION_DIR / "storage_state.json"
SESSION_MAX_AGE_DAYS = 7
EMS_URL = "https://ucsdevents.emscloudservice.com/web/"
SAML_URL = "https://ucsdevents.emscloudservice.com/web/samlauth.aspx"
DUO_TIMEOUT_MS = 60_000
KEYRING_SERVICE = "study-room-booking"
KEYRING_USERNAME_KEY = "ucsd-sso-username"


def save_credentials(username: str, password: str) -> None:
    try:
        keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, username)
        keyring.set_password(KEYRING_SERVICE, username, password)
    except Exception:
        print("Warning: Could not save credentials to system keyring. "
              "Credentials will not be remembered for auto-login.")


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
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "cookies": cookies,
        "created_at": datetime.now().isoformat(),
    }
    path.write_text(json.dumps(data, indent=2))


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


async def _sso_login(page, username: str, password: str) -> None:
    """Fill the UCSD SSO form, then wait for Duo Push approval and the EMS redirect.

    Duo sends the push automatically. Clicks "Yes, this is my device" on the trust
    prompt so it works headless.
    """
    await page.locator("#ssousername").fill(username)
    await page.locator("#ssopassword").fill(password)
    await page.locator("button[type='submit']").click()
    print("Duo Push sent. Please approve on your phone...")

    trust_button = page.get_by_role("button", name="Yes, this is my device")
    loop = asyncio.get_running_loop()
    deadline = loop.time() + DUO_TIMEOUT_MS / 1000
    sso_error_check_after = loop.time() + 5
    while loop.time() < deadline:
        await asyncio.sleep(0.5)
        if _on_ems(page.url):
            await page.wait_for_load_state("networkidle")
            return
        try:
            if await trust_button.count() > 0:
                await trust_button.click()
            # Still on the SSO form after submit → wrong username/password
            elif loop.time() > sso_error_check_after and await page.locator("#ssousername").is_visible():
                raise LoginError("SSO login failed. Check your username/password and run 'study-room login'.")
        except PlaywrightError:
            continue  # page navigating mid-check
    raise LoginError("Timed out waiting for Duo approval.")


async def _save_storage(context, session_path: Path) -> list:
    cookies = await context.cookies()
    save_session(cookies, session_path)
    await context.storage_state(path=str(session_path.parent / "storage_state.json"))
    return cookies


async def login(username: str, password: str, session_path: Path = SESSION_PATH) -> list:
    """Headless SSO login + Duo Push authentication. Saves credentials and cookies on success."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, channel="chrome")
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(SAML_URL)
        await page.wait_for_load_state("networkidle")
        await page.wait_for_selector("#ssousername", timeout=15000)
        await _sso_login(page, username, password)

        save_credentials(username, password)
        cookies = await _save_storage(context, session_path)
        print(f"Login successful! {len(cookies)} cookies + storage state saved.")

        await browser.close()
        return cookies


async def get_authenticated_context(playwright, session_path: Path = SESSION_PATH, headless: bool = True, channel: str | None = "chrome"):
    """Return a browser context with saved storage state.

    If the session is stale but keychain credentials exist, returns a blank context
    and lets authenticate() log in headlessly. Returns None if neither is available.
    """
    session_valid = is_session_valid(session_path)
    if not session_valid and load_credentials() is None:
        return None

    storage_state_path = session_path.parent / "storage_state.json"
    launch_args = {"headless": headless}
    if channel:
        launch_args["channel"] = channel
    browser = await playwright.chromium.launch(**launch_args)

    if not session_valid:
        context = await browser.new_context()
    elif storage_state_path.exists():
        context = await browser.new_context(storage_state=str(storage_state_path))
    else:
        session = load_session(session_path)
        context = await browser.new_context()
        await context.add_cookies(session["cookies"])

    return context


async def authenticate(page, session_path: Path = SESSION_PATH) -> None:
    """SAML authentication. Auto-passes if SSO is valid, otherwise logs in headlessly from keychain."""
    print("Authenticating via SAML...")

    await page.goto(SAML_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    if await page.locator("#ssousername").count() > 0:
        creds = load_credentials()
        if creds is None:
            raise SessionExpiredError("SSO session expired. Please run 'study-room login'.")
        print("SSO session expired. Logging in with saved credentials...")
        await _sso_login(page, *creds)
    else:
        # SSO valid → auto-redirects to EMS
        await page.wait_for_url("**/web/**", timeout=15000)

    await _save_storage(page.context, session_path)
    print("Authentication complete.")
