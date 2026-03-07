"""
Headless mode (channel='chrome', headless=True) EMS 검색 테스트.

사전 조건: `study-room login`으로 세션이 저장되어 있어야 함.

실행: .venv/bin/python tests/test_headless_search.py [DATE]
  DATE 생략 시 모레 날짜 사용
"""
import asyncio
import sys
from datetime import date, timedelta

from playwright.async_api import async_playwright

from study_room.auth import get_authenticated_context, is_session_valid, authenticate
from study_room.booking import (
    _format_date,
    _format_time,
    _navigate_to_search,
    _check_search_loaded,
    _parse_available_rooms,
)
from study_room.config import load_config


async def run_headless_search(test_date: str):
    config = load_config()
    target_rooms = set(config["rooms"])
    formatted_date = _format_date(test_date)
    formatted_start = _format_time("14:00")
    formatted_end = _format_time("16:00")

    print(f"=== Headless Search Test ===")
    print(f"Date: {test_date} ({formatted_date})")
    print(f"Time: {formatted_start} - {formatted_end}")
    print(f"Mode: channel='chrome', headless=True")
    print()

    # 세션 확인
    if not is_session_valid():
        print("ERROR: 세션이 없거나 만료됨. 'study-room login' 먼저 실행.")
        return False

    async with async_playwright() as p:
        # headless=True로 브라우저 열기
        context = await get_authenticated_context(p, headless=True, channel="chrome")
        if context is None:
            print("ERROR: 인증된 컨텍스트 생성 실패.")
            return False

        page = await context.new_page()
        try:
            print("[1/4] SAML 인증 중...")
            await authenticate(page)

            print("[2/4] EMS 접속 + 검색 중...")
            await _navigate_to_search(page, formatted_date, formatted_start, formatted_end)

            print("[3/4] 검색 결과 확인 중...")
            loaded = await _check_search_loaded(page)

            if not loaded:
                print("FAIL: 검색 결과가 로드되지 않음 (봇 감지 가능성)")
                print(f"  현재 URL: {page.url}")
                title = await page.title()
                print(f"  페이지 제목: {title}")
                return False

            print("[4/4] 방 목록 파싱 중...")
            rooms = await _parse_available_rooms(page, target_rooms)

            print()
            print(f"SUCCESS: headless 검색 성공!")
            print(f"  빈 방 {len(rooms)}개:")
            for room in rooms:
                print(f"    - {room.name}")
            return True

        except Exception as e:
            print(f"ERROR: {type(e).__name__}: {e}")
            print(f"  현재 URL: {page.url}")
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
