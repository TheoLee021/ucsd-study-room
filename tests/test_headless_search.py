"""
EMS search test in headless mode (channel='chrome', headless=True).

Prerequisite: a session saved via `study-room login`.

Usage: .venv/bin/python tests/test_headless_search.py [DATE]
  DATE defaults to two days from today
"""

import asyncio
import sys
from datetime import date, timedelta

from playwright.async_api import async_playwright

from study_room.auth import authenticate, get_authenticated_context, is_session_valid
from study_room.booking import (
    _check_search_loaded,
    _format_date,
    _format_time,
    _navigate_to_search,
    _parse_search_payloads,
)
from study_room.config import load_config


async def run_headless_search(test_date: str):
    config = load_config()
    target_rooms = set(config["rooms"])
    formatted_date = _format_date(test_date)
    formatted_start = _format_time("14:00")
    formatted_end = _format_time("16:00")

    print("=== Headless Search Test ===")
    print(f"Date: {test_date} ({formatted_date})")
    print(f"Time: {formatted_start} - {formatted_end}")
    print("Mode: channel='chrome', headless=True")
    print()

    # Check session
    if not is_session_valid():
        print("ERROR: No session or session expired. Run 'study-room login' first.")
        return False

    async with async_playwright() as p:
        # Open browser with headless=True
        context = await get_authenticated_context(p, headless=True, channel="chrome")
        if context is None:
            print("ERROR: Failed to create authenticated context.")
            return False

        page = await context.new_page()
        try:
            print("[1/4] Authenticating via SAML...")
            await authenticate(page)

            print("[2/4] Opening EMS and searching...")
            payloads = await _navigate_to_search(
                page, formatted_date, formatted_start, formatted_end
            )

            print("[3/4] Checking search results...")
            loaded = await _check_search_loaded(page)

            if not loaded:
                print("FAIL: Search results did not load (possible bot detection)")
                print(f"  Current URL: {page.url}")
                title = await page.title()
                print(f"  Page title: {title}")
                return False

            print("[4/4] Parsing room list...")
            if payloads is None:
                print("FAIL: EMS availability API responses were not captured")
                return False
            result = _parse_search_payloads(
                *payloads, test_date, "14:00", "16:00", target_rooms
            )

            print()
            print("SUCCESS: Headless search succeeded!")
            print(f"  {len(result.rooms)} free room(s):")
            for room in result.rooms:
                status = "bookable" if room.bookable else result.blocked_reason(room)
                print(f"    - {room.name} ({status})")
            return True

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            print(f"  Current URL: {page.url}")
            return False
        finally:
            await context.browser.close()


if __name__ == "__main__":
    if len(sys.argv) > 1:
        test_date = sys.argv[1]
    else:
        test_date = (date.today() + timedelta(days=2)).isoformat()

    result = asyncio.run(run_headless_search(test_date))
    sys.exit(0 if result else 1)
