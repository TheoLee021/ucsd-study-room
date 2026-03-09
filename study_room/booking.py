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
    """Clear an input field and fill with a new value."""
    el = page.locator(selector)
    await el.click(click_count=3)
    await el.press(_SELECT_ALL)
    await el.fill(value)
    await el.press("Tab")


async def _navigate_to_search(page: Page, date: str, start_time: str, end_time: str):
    """EMS main → Book Now → fill date/time → click Search."""
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
    """Check if search results loaded successfully."""
    room_results = page.locator(".column-text.available a.location, .column-text.unavailable a.location")
    return await room_results.count() > 0


async def _search_with_retry(page: Page, date: str, start_time: str, end_time: str) -> Page:
    """SAML auth → search + retry with re-login on failure. Returns None if headed re-login occurred."""
    result = await authenticate(page)
    if result == "relogin_needed":
        return None  # caller retries with new context

    await _navigate_to_search(page, date, start_time, end_time)

    if not await _check_search_loaded(page):
        result = await authenticate(page)
        if result == "relogin_needed":
            return None
        await _navigate_to_search(page, date, start_time, end_time)
        if not await _check_search_loaded(page):
            raise BookingError("Failed to load search results. Please try again later.")

    return page


async def _parse_available_rooms(page: Page, target_rooms: set[str]) -> list[Room]:
    """Return only rooms whose add-to-cart button is visible."""
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
    """Headless browser search. Recursively retries if headed re-login occurs."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login'.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            # Headed re-login complete → retry with new context
            return await _open_and_search(playwright, date, start_time, end_time, target_rooms)
        return await _parse_available_rooms(page, target_rooms)
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def search_rooms(date: str, start_time: str, end_time: str) -> list[Room]:
    """Search for available rooms on EMS. Opens and closes its own browser."""
    config = load_config()
    target_rooms = set(config["rooms"])
    formatted_date = _format_date(date)
    formatted_start = _format_time(start_time)
    formatted_end = _format_time(end_time)

    async with async_playwright() as p:
        return await _open_and_search(p, formatted_date, formatted_start, formatted_end, target_rooms)


async def _open_search_and_book(playwright, date: str, start_time: str, end_time: str, room_name: str, config: dict) -> str:
    """Headless browser search + book. Recursively retries if headed re-login occurs."""
    formatted_start = _format_time(start_time.replace("/", ":")) if "/" in start_time else start_time
    formatted_end = _format_time(end_time.replace("/", ":")) if "/" in end_time else end_time

    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login'.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            return await _open_search_and_book(playwright, date, start_time, end_time, room_name, config)

        # Check room availability + click
        add_btn = page.locator(f'i.book-add-to-cart[aria-label*="{room_name}"]')
        if await add_btn.count() == 0 or not await add_btn.first.is_visible():
            raise BookingError(f"'{room_name}' is not available for the selected time.")
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

        return f"Booking confirmed: {room_name}"
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def book_room(date: str, start_time: str, end_time: str, room_name: str) -> str:
    """Search → select room → book in a single browser session."""
    config = load_config()
    if room_name not in config["rooms"]:
        raise BookingError(f"'{room_name}' is not a supported room.")

    formatted_date = _format_date(date)
    formatted_start = _format_time(start_time)
    formatted_end = _format_time(end_time)

    async with async_playwright() as p:
        return await _open_search_and_book(p, formatted_date, formatted_start, formatted_end, room_name, config)


async def _open_search_and_book_interactive(playwright, date: str, start_time: str, end_time: str, target_rooms: set[str], config: dict, room_selector=None) -> str:
    """Headless browser search → select → book. Recursively retries if headed re-login occurs."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login'.")

    page = await context.new_page()
    try:
        page = await _search_with_retry(page, date, start_time, end_time)
        if page is None:
            return await _open_search_and_book_interactive(playwright, date, start_time, end_time, target_rooms, config, room_selector)

        rooms = await _parse_available_rooms(page, target_rooms)

        if not rooms:
            raise BookingError("No rooms available for the selected time.")

        if room_selector:
            selected = await room_selector(rooms)
            if selected is None:
                return "Booking cancelled."
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

        return f"Booking confirmed: {selected.name} ({date} {start_time}-{end_time})"
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def search_and_book(date: str, start_time: str, end_time: str, room_selector=None) -> str:
    """
    Search → user selection → book in a single browser session.

    Args:
        room_selector: async callable(rooms) -> Room or None
            Callback for user to select a room. If None, selects the first room.
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
    """Parse current reservations from the MY EVENTS page via headless browser."""
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
    """List current reservations."""
    async with async_playwright() as p:
        return await _open_and_get_events(p)
