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
    keyring.set_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY, username)
    keyring.set_password(KEYRING_SERVICE, username, password)


def load_credentials() -> tuple[str, str] | None:
    username = keyring.get_password(KEYRING_SERVICE, KEYRING_USERNAME_KEY)
    if username is None:
        return None
    password = keyring.get_password(KEYRING_SERVICE, username)
    if password is None:
        return None
    return username, password


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
    """SSO 로그인 + Duo Push 인증 후 쿠키를 저장한다."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, channel="chrome")
        context = await browser.new_context()
        page = await context.new_page()

        # 1. SAML 인증 페이지로 직접 이동 → UCSD SSO 리다이렉트
        await page.goto(SAML_URL)
        await page.wait_for_load_state("networkidle")

        # 2. UCSD SSO 로그인 — username + password
        await page.wait_for_selector("#ssousername", timeout=15000)
        await page.locator("#ssousername").fill(username)
        await page.locator("#ssopassword").fill(password)
        await page.locator("button[type='submit']").click()

        # 3. Duo Push 대기 — EMS 페이지로 돌아오면 인증 완료
        print("Duo Push가 전송되었습니다. 폰에서 승인해주세요...")
        await page.wait_for_url("**/web/**", timeout=DUO_TIMEOUT_MS)

        # 4. credentials를 keychain에 저장
        save_credentials(username, password)

        # 5. storage state 전체 저장 (쿠키 + localStorage + sessionStorage)
        cookies = await context.cookies()
        save_session(cookies, session_path)

        storage_state_path = session_path.parent / "storage_state.json"
        await context.storage_state(path=str(storage_state_path))
        print(f"로그인 성공! {len(cookies)}개 쿠키 + storage state 저장됨.")

        await browser.close()
        return cookies


async def get_authenticated_context(playwright, session_path: Path = SESSION_PATH, headless: bool = True, channel: str | None = "chrome"):
    """저장된 storage state로 인증된 브라우저 컨텍스트를 반환한다."""
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
    """SSO 만료 시 headed 브라우저로 재로그인. Keychain → 자동입력, 실패 → 수동입력."""
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
            print("Keychain에서 credentials 로드 → 자동 입력 중...")
            await page.locator("#ssousername").fill(username)
            await page.locator("#ssopassword").fill(password)
            await page.locator("button[type='submit']").click()
        else:
            print("Keychain에 credentials 없음 → 브라우저에서 직접 로그인해주세요.")

        print("Duo Push가 전송되었습니다. 폰에서 승인해주세요...")
        await page.wait_for_url("**/web/**", timeout=DUO_TIMEOUT_MS)

        # 세션 저장
        cookies = await context.cookies()
        save_session(cookies, session_path)
        storage_state_path = session_path.parent / "storage_state.json"
        await context.storage_state(path=str(storage_state_path))
        print("재로그인 성공! 세션 갱신됨.")

        await browser.close()


async def authenticate(page, session_path: Path = SESSION_PATH):
    """SAML 인증. SSO 유효 시 자동 통과, 만료 시 headed 브라우저로 Duo 인증."""
    import asyncio

    print("SAML 인증 중...")

    await page.goto(SAML_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(2)

    # SSO 로그인 페이지가 나왔는지 확인
    sso_form = page.locator("#ssousername")
    if await sso_form.count() > 0:
        # SSO 만료 — headed 브라우저로 Duo 인증
        print("SSO 세션 만료. headed 브라우저로 로그인 진행...")
        await page.context.browser.close()
        await _headed_login_and_save(session_path)
        return "relogin_needed"

    # SSO 유효 → 자동으로 EMS 리다이렉트
    await page.wait_for_url("**/web/**", timeout=15000)

    # storage state 갱신
    context = page.context
    cookies = await context.cookies()
    save_session(cookies, session_path)
    storage_state_path = session_path.parent / "storage_state.json"
    await context.storage_state(path=str(storage_state_path))
    print("인증 완료.")


class SessionExpiredError(Exception):
    pass
