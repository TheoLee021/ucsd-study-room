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
    time: str
    room: str
    status: str
    reservation_id: str


CANCEL_REASONS = [
    "Bad Weather",
    "Changed Date",
    "Changed Location",
    "Lack of Funding",
    "Lack of Interest",
    "Lack of Resources",
    "Lack of Time to Plan",
    "Other",
]


@dataclass
class CancelResult:
    status: str  # "cancelled", "needs_selection", "error"
    message: str
    reservations: list[Reservation] | None = None


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

        # Collect basic info and name links from My Events table
        entries = []
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
            entries.append({
                "index": i,
                "date": date_text,
                "room": room,
                "reservation_id": reservation_id,
                "status": status,
            })

        # Navigate to each detail page to get time info
        reservations = []
        for entry in entries:
            row = rows.nth(entry["index"])
            name_link = row.locator("td").nth(0).locator("a")
            await name_link.click()
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)

            # Parse Bookings table (table-sort): EDIT | REMOVE | DATE | START TIME | END TIME | ...
            time_text = ""
            booking_rows = page.locator("table.table-sort tbody tr")
            if await booking_rows.count() > 0:
                booking_cols = booking_rows.nth(0).locator("td")
                if await booking_cols.count() >= 5:
                    start_text = (await booking_cols.nth(3).inner_text()).strip()
                    end_text = (await booking_cols.nth(4).inner_text()).strip()
                    time_text = f"{start_text} - {end_text}"

            reservations.append(Reservation(
                date=entry["date"],
                time=time_text,
                room=entry["room"],
                status=entry["status"],
                reservation_id=entry["reservation_id"],
            ))

            # Go back to My Events list
            await page.goto(MY_EVENTS_URL)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(2)
            # Re-locate rows after navigation
            rows = page.locator("table.table tbody tr")

        return reservations
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def my_events() -> list[Reservation]:
    """List current reservations."""
    async with async_playwright() as p:
        return await _open_and_get_events(p)


async def _open_and_cancel(playwright, date: str, room_name: str | None, reason: str) -> CancelResult:
    """Navigate My Events → find reservation → cancel. Recursively retries on headed re-login."""
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login' first.")

    page = await context.new_page()
    try:
        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")

        result = await authenticate(page)
        if result == "relogin_needed":
            return await _open_and_cancel(playwright, date, room_name, reason)

        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Parse rows and find matching reservations
        rows = page.locator("table.table tbody tr")
        count = await rows.count()

        matching_rows = []
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

            if date in date_text:
                if room_name and room_name not in room:
                    continue
                matching_rows.append({
                    "index": i,
                    "reservation": Reservation(date=date_text, time="", room=room, status=status, reservation_id=reservation_id),
                })

        if not matching_rows:
            return CancelResult(status="error", message=f"No reservation found for {date}.")

        if len(matching_rows) > 1 and room_name is None:
            return CancelResult(
                status="needs_selection",
                message=f"Multiple reservations found for {date}. Please specify a room.",
                reservations=[m["reservation"] for m in matching_rows],
            )

        target = matching_rows[0]

        # Click name link in cols[0] → navigate to ReservationSummary
        target_row = rows.nth(target["index"])
        name_link = target_row.locator("td").nth(0).locator("a")
        await name_link.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        # Check if Cancel Reservation button exists
        cancel_link = page.locator("a:has-text('Cancel Reservation')")
        if await cancel_link.count() == 0:
            return CancelResult(
                status="error",
                message="Cannot cancel this reservation (cancel option not available).",
            )

        # Execute cancellation
        await cancel_link.click()
        await asyncio.sleep(2)

        # Select cancel reason from dropdown
        await page.select_option("select", label=reason)
        await asyncio.sleep(1)

        # Click "Yes, Cancel Reservation"
        await page.locator("button:has-text('Yes, Cancel Reservation')").click()
        await asyncio.sleep(3)

        res = target["reservation"]
        return CancelResult(
            status="cancelled",
            message=f"Cancelled: {res.room} on {res.date} (ID: {res.reservation_id}).",
        )
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


def _format_date_for_match(date_iso: str) -> str:
    """YYYY-MM-DD → 'Mar 13, 2026' for substring matching against EMS date text."""
    from datetime import datetime as _dt
    dt = _dt.strptime(date_iso, "%Y-%m-%d")
    return f"{dt.strftime('%b')} {dt.day}, {dt.year}"


async def cancel_reservation(date: str, room_name: str | None = None, reason: str = "Changed Date") -> CancelResult:
    """Cancel a reservation by date. Optionally filter by room_name.

    Args:
        date: YYYY-MM-DD format (from CLI --date or MCP) or raw date text (from interactive picker).
    """
    # ISO format (YYYY-MM-DD) → convert to 'Mar 13, 2026'; otherwise pass through as-is
    if len(date) == 10 and date[4:5] == "-" and date[7:8] == "-":
        match_date = _format_date_for_match(date)
    else:
        match_date = date
    async with async_playwright() as p:
        return await _open_and_cancel(p, match_date, room_name, reason)
