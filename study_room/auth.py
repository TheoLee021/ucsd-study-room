import json
from datetime import datetime, timedelta
from pathlib import Path

import keyring
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


async def login(username: str, password: str, session_path: Path = SESSION_PATH) -> list:
    """SSO login + Duo Push authentication. Saves cookies on success."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context()
        page = await context.new_page()

        # 1. Navigate to SAML auth page → redirects to UCSD SSO
        await page.goto(SAML_URL)
        await page.wait_for_load_state("networkidle")

        # 2. UCSD SSO login — username + password
        await page.wait_for_selector("#ssousername", timeout=15000)
        await page.locator("#ssousername").fill(username)
        await page.locator("#ssopassword").fill(password)
        await page.locator("button[type='submit']").click()

        # 3. Wait for Duo Push — authentication complete when redirected to EMS
        print("Duo Push sent. Please approve on your phone...")
        await page.wait_for_url("**/web/**", timeout=DUO_TIMEOUT_MS)

        # 4. Save credentials to keychain
        save_credentials(username, password)

        # 5. Save full storage state (cookies + localStorage + sessionStorage)
        cookies = await context.cookies()
        save_session(cookies, session_path)

        storage_state_path = session_path.parent / "storage_state.json"
        await context.storage_state(path=str(storage_state_path))
        print(f"Login successful! {len(cookies)} cookies + storage state saved.")

        await browser.close()
        return cookies


async def get_authenticated_context(playwright, session_path: Path = SESSION_PATH, headless: bool = True, channel: str | None = "chrome"):
    """Return an authenticated browser context using saved storage state."""
    if not is_session_valid(session_path):
        return None

    storage_state_path = session_path.parent / "storage_state.json"
    launch_args = {"headless": headless}
    if channel:
        launch_args["channel"] = channel
    browser = await playwright.chromium.launch(**launch_args)

    if storage_state_path.exists():
        context = await browser.new_context(storage_state=str(storage_state_path))
    else:
        session = load_session(session_path)
        context = await browser.new_context()
        await context.add_cookies(session["cookies"])

    return context


async def _headed_login_and_save(session_path: Path = SESSION_PATH):
    """Re-login via headed browser when SSO expires. Auto-fills from keychain if available."""
    import asyncio

    creds = load_credentials()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context()
        page = await context.new_page()

        await page.goto(SAML_URL)
        await page.wait_for_load_state("networkidle")

        await page.wait_for_selector("#ssousername", timeout=15000)

        if creds:
            username, password = creds
            print("Loaded credentials from keychain. Auto-filling...")
            await page.locator("#ssousername").fill(username)
            await page.locator("#ssopassword").fill(password)
            await page.locator("button[type='submit']").click()
        else:
            print("No credentials in keychain. Please log in manually in the browser.")

        print("Duo Push sent. Please approve on your phone...")
        await page.wait_for_url("**/web/**", timeout=DUO_TIMEOUT_MS)

        # Save session
        cookies = await context.cookies()
        save_session(cookies, session_path)
        storage_state_path = session_path.parent / "storage_state.json"
        await context.storage_state(path=str(storage_state_path))
        print("Re-login successful! Session renewed.")

        await browser.close()


async def authenticate(page, session_path: Path = SESSION_PATH):
    """SAML authentication. Auto-passes if SSO is valid, opens headed browser for Duo if expired."""
    import asyncio

    print("Authenticating via SAML...")

    await page.goto(SAML_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    # Check if SSO login page appeared
    sso_form = page.locator("#ssousername")
    if await sso_form.count() > 0:
        # SSO expired — open headed browser for Duo auth
        print("SSO session expired. Opening browser for login...")
        await page.context.browser.close()
        await _headed_login_and_save(session_path)
        return "relogin_needed"

    # SSO valid → auto-redirects to EMS
    await page.wait_for_url("**/web/**", timeout=15000)

    # Refresh storage state
    context = page.context
    cookies = await context.cookies()
    save_session(cookies, session_path)
    storage_state_path = session_path.parent / "storage_state.json"
    await context.storage_state(path=str(storage_state_path))
    print("Authentication complete.")


class SessionExpiredError(Exception):
    pass
