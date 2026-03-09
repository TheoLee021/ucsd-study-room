import asyncio
import platform
from dataclasses import dataclass
from playwright.async_api import async_playwright, Page, BrowserContext

from study_room.auth import get_authenticated_context, authenticate, EMS_URL, SessionExpiredError
from study_room.config import load_config

_SELECT_ALL = "Meta+a" if platform.system() == "Darwin" else "Control+a"


@dataclass
class Room:
    name: str
    available: bool


@dataclass
class Reservation:
    date: str
    room: str
    status: str
    reservation_id: str


class DateUnavailableError(Exception):
    pass


class BookingError(Exception):
    pass


async def _fill_input(page: Page, selector: str, value: str):
    """입력 필드의 기존 값을 지우고 새 값을 입력한다."""
    el = page.locator(selector)
    await el.click(click_count=3)
    await el.press(_SELECT_ALL)
    await el.fill(value)
    await el.press("Tab")


async def _navigate_to_search(page: Page, date: str, start_time: str, end_time: str):
    """EMS 메인 → Book Now → 날짜/시간 입력 → Search 클릭."""
    await page.goto(EMS_URL)
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    await page.locator("button:has-text('book now')").first.click()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    await _fill_input(page, "#booking-date-input", date)
    await asyncio.sleep(1)
    await _fill_input(page, "#start-time-input", start_time)
    await asyncio.sleep(0.5)
    await _fill_input(page, "#end-time-input", end_time)
    await asyncio.sleep(0.5)

    await page.locator("button.find-a-room").first.click()
    await page.wait_for_load_state("networkidle")
    await asyncio.sleep(3)


async def _check_search_loaded(page: Page) -> bool:
    """검색 결과가 정상적으로 로드됐는지 확인한다."""
    room_results = page.locator(".column-text.available a.location, .column-text.unavailable a.location")
    return await room_results.count() > 0


async def _search_with_retry(page: Page, date: str, start_time: str, end_time: str) -> Page:
    """SAML 인증 → 검색 + 실패 시 재로그인 후 재시도. headed 재로그인 시 새 page 반환."""
    result = await authenticate(page)
    if result == "relogin_needed":
        return None  # caller가 새 컨텍스트로 재시도

    await _navigate_to_search(page, date, start_time, end_time)

    if not await _check_search_loaded(page):
        result = await authenticate(page)
        if result == "relogin_needed":
            return None
        await _navigate_to_search(page, date, start_time, end_time)
        if not await _check_search_loaded(page):
            raise BookingError("검색 결과를 불러올 수 없습니다. 나중에 다시 시도해주세요.")

    return page


async def _parse_available_rooms(page: Page, target_rooms: set[str]) -> list[Room]:
    """+버튼이 visible인 방만 반환."""
    rooms = []
    for room_name in sorted(target_rooms):
        add_btn = page.locator(f'i.book-add-to-cart[aria-label*="{room_name}"]')
        if await add_btn.count() > 0 and await add_btn.first.is_visible():
            rooms.append(Room(name=room_name, available=True))
    return rooms


def _format_date(date_iso: str) -> str:
    """YYYY-MM-DD → MM/DD/YYYY"""
    parts = date_iso.split("-")
    return f"{parts[1]}/{parts[2]}/{parts[0]}"


def _format_time(time_24h: str) -> str:
    """HH:MM (24h) → h:mm AM/PM"""
    h, m = map(int, time_24h.split(":"))
    period = "AM" if h < 12 else "PM"
    if h == 0:
        h = 12
    elif h > 12:
        h -= 12
    return f"{h}:{m:02d} {period}"


# === Public API ===


async def _open_and_search(playwright, date: str, start_time: str, end_time: str, target_rooms: set[str]) -> list[Room]:
    """헤드리스 브라우저로 검색. headed 재로그인 발생 시 재귀 재시도."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("세션이 만료됐습니다. 'study-room login'을 실행해주세요.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            # headed 재로그인 완료 → 새 컨텍스트로 재시도
            return await _open_and_search(playwright, date, start_time, end_time, target_rooms)
        return await _parse_available_rooms(page, target_rooms)
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def search_rooms(date: str, start_time: str, end_time: str) -> list[Room]:
    """EMS에서 빈 방을 검색한다. (단독 사용 — 브라우저를 열고 닫는다)"""
    config = load_config()
    target_rooms = set(config["rooms"])
    formatted_date = _format_date(date)
    formatted_start = _format_time(start_time)
    formatted_end = _format_time(end_time)

    async with async_playwright() as p:
        return await _open_and_search(p, formatted_date, formatted_start, formatted_end, target_rooms)


async def _open_search_and_book(playwright, date: str, start_time: str, end_time: str, room_name: str, config: dict) -> str:
    """헤드리스 브라우저로 검색+예약. headed 재로그인 발생 시 재귀 재시도."""
    formatted_start = _format_time(start_time.replace("/", ":")) if "/" in start_time else start_time
    formatted_end = _format_time(end_time.replace("/", ":")) if "/" in end_time else end_time

    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("세션이 만료됐습니다. 'study-room login'을 실행해주세요.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            return await _open_search_and_book(playwright, date, start_time, end_time, room_name, config)

        # 방 available 확인 + 클릭
        add_btn = page.locator(f'i.book-add-to-cart[aria-label*="{room_name}"]')
        if await add_btn.count() == 0 or not await add_btn.first.is_visible():
            raise BookingError(f"'{room_name}'은 해당 시간에 예약할 수 없습니다.")
        await add_btn.click()
        await asyncio.sleep(1)

        await page.locator("#setup--add-modal-save").click()
        await asyncio.sleep(2)

        await page.locator("#next-step-btn").click()
        await asyncio.sleep(5)

        await page.locator("#event-name").fill(config["name"])
        await page.locator('[id="1stContactName"]').fill(config["name"])
        await page.locator('[id="1stContactEmail"]').fill(config["email"])
        await page.locator("#terms-and-conditions").check()
        await asyncio.sleep(1)

        await page.locator("button:has-text('Create Reservation')").first.click()
        await asyncio.sleep(5)

        return f"{room_name} 예약 완료"
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def book_room(date: str, start_time: str, end_time: str, room_name: str) -> str:
    """검색 → 방 선택 → 예약까지 하나의 브라우저에서 진행한다."""
    config = load_config()
    if room_name not in config["rooms"]:
        raise BookingError(f"'{room_name}'은 지원하는 방이 아닙니다.")

    formatted_date = _format_date(date)
    formatted_start = _format_time(start_time)
    formatted_end = _format_time(end_time)

    async with async_playwright() as p:
        return await _open_search_and_book(p, formatted_date, formatted_start, formatted_end, room_name, config)


async def _open_search_and_book_interactive(playwright, date: str, start_time: str, end_time: str, target_rooms: set[str], config: dict, room_selector=None) -> str:
    """헤드리스 브라우저로 검색→선택→예약. headed 재로그인 발생 시 재귀 재시도."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("세션이 만료됐습니다. 'study-room login'을 실행해주세요.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            return await _open_search_and_book_interactive(playwright, date, start_time, end_time, target_rooms, config, room_selector)

        rooms = await _parse_available_rooms(page, target_rooms)

        if not rooms:
            raise BookingError("해당 시간에 빈 방이 없습니다.")

        if room_selector:
            selected = await room_selector(rooms)
            if selected is None:
                return "예약 취소됨."
        else:
            selected = rooms[0]

        add_btn = page.locator(f'i.book-add-to-cart[aria-label*="{selected.name}"]')
        await add_btn.click()
        await asyncio.sleep(1)

        await page.locator("#setup--add-modal-save").click()
        await asyncio.sleep(2)

        await page.locator("#next-step-btn").click()
        await asyncio.sleep(5)

        await page.locator("#event-name").fill(config["name"])
        await page.locator('[id="1stContactName"]').fill(config["name"])
        await page.locator('[id="1stContactEmail"]').fill(config["email"])
        await page.locator("#terms-and-conditions").check()
        await asyncio.sleep(1)

        await page.locator("button:has-text('Create Reservation')").first.click()
        await asyncio.sleep(5)

        return f"{selected.name} 예약 완료 ({date} {start_time}-{end_time})"
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def search_and_book(date: str, start_time: str, end_time: str, room_selector=None) -> str:
    """
    하나의 브라우저 세션에서 검색 → 유저 선택 → 예약을 진행한다.

    Args:
        room_selector: async callable(rooms) -> Room 또는 None
            유저에게 방을 선택받는 콜백. None이면 첫 번째 방을 선택.
    """
    config = load_config()
    target_rooms = set(config["rooms"])
    formatted_date = _format_date(date)
    formatted_start = _format_time(start_time)
    formatted_end = _format_time(end_time)

    async with async_playwright() as p:
        return await _open_search_and_book_interactive(p, formatted_date, formatted_start, formatted_end, target_rooms, config, room_selector)


MY_EVENTS_URL = "https://ucsdevents.emscloudservice.com/web/BrowseReservations.aspx"


async def _open_and_get_events(playwright) -> list[Reservation]:
    """헤드리스 브라우저로 MY EVENTS 페이지에서 현재 예약 목록을 파싱한다."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login' first.")

    page = await context.new_page()
    try:
        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")

        result = await authenticate(page)
        if result == "relogin_needed":
            return await _open_and_get_events(playwright)

        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        rows = page.locator("table.table tbody tr")
        count = await rows.count()

        reservations = []
        for i in range(count):
            row = rows.nth(i)
            cols = row.locator("td")
            if await cols.count() < 7:
                continue

            date_text = (await cols.nth(1).inner_text()).strip().split("/")[0].strip()
            location_text = (await cols.nth(2).inner_text()).strip()
            room = location_text.split(" - ")[-1].strip() if " - " in location_text else location_text
            reservation_id = (await cols.nth(5).inner_text()).strip()
            status = (await cols.nth(6).inner_text()).strip()

            reservations.append(Reservation(
                date=date_text,
                room=room,
                status=status,
                reservation_id=reservation_id,
            ))

        return reservations
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def my_events() -> list[Reservation]:
    """현재 예약 목록을 조회한다."""
    async with async_playwright() as p:
        return await _open_and_get_events(p)
