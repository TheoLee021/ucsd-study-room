import asyncio
import json
from pathlib import Path

import pytest

from study_room import booking
from study_room.booking import (
    BookingError,
    Room,
    SearchResult,
    _parse_search_payloads,
)

FIXTURES = Path(__file__).parent / "fixtures"
TARGET = {f"Price Center Study Room {i}" for i in range(1, 9)}


def _load(name):
    data = json.loads((FIXTURES / f"ems_search_{name}.json").read_text())
    return data["rooms"], data["bookings"]


def _payloads(rooms, bookings):
    wrap = lambda obj: {"d": json.dumps(obj)}  # noqa: E731
    return (
        wrap({"Buildings": [{"Rooms": rooms}]}),
        wrap({"Bookings": bookings}),
    )


def _room(id_, reason, name=None):
    return {
        "Id": id_,
        "DisplayText": name or f"Price Center Study Room {id_}",
        "UnavailableReason": reason,
        "SetupHours": 0.25,
        "TeardownHours": 0.25,
    }


def _booking(room_id, start, end, mine=False):
    return {
        "RoomId": room_id,
        "EventStart": f"2026-11-03T{start}:00",
        "EventEnd": f"2026-11-03T{end}:00",
        "TimeBookingStart": f"2026-11-03T{start}:00",
        "TimeBookingEnd": f"2026-11-03T{end}:00",
        "WebUserIsOwner": mine,
    }


def test_own_booking_day_reports_free_rooms_as_blocked():
    # Real EMS data: every room has reason 11 because of the user's own booking.
    result = _parse_search_payloads(
        *_load("own_booking_day"), "2026-11-02", "18:00", "19:00", TARGET
    )
    assert [r.name for r in result.rooms] == [
        "Price Center Study Room 3",
        "Price Center Study Room 5",
        "Price Center Study Room 6",
    ]
    assert result.bookable_rooms == []
    assert result.my_bookings == ["Price Center Study Room 2, 10:00 AM-2:00 PM"]
    assert result.no_bookable_message() == (
        "Free but not bookable: Price Center Study Room 3, Price Center Study Room 5, "
        "Price Center Study Room 6 - you already have a reservation that day "
        "(Price Center Study Room 2, 10:00 AM-2:00 PM)."
    )


def test_normal_day_uses_reason_codes():
    result = _parse_search_payloads(
        *_load("no_own_booking_day"), "2026-11-03", "18:00", "19:00", TARGET
    )
    assert [r.name for r in result.bookable_rooms] == [
        f"Price Center Study Room {i}" for i in range(3, 9)
    ]
    assert result.blocked_rooms == []
    assert result.my_bookings == []


def test_only_target_rooms_are_returned():
    result = _parse_search_payloads(
        *_load("no_own_booking_day"),
        "2026-11-03",
        "18:00",
        "19:00",
        {"Price Center Study Room 3"},
    )
    assert [r.name for r in result.rooms] == ["Price Center Study Room 3"]


def test_overlap_accounts_for_setup_and_teardown():
    rooms = [_room(1, 11), _room(2, 11), _room(3, 11)]
    bookings = [
        _booking(1, "16:00", "17:45"),  # ends right at 18:00 minus setup: free
        _booking(2, "16:00", "17:50"),  # runs into setup buffer: busy
        _booking(3, "19:15", "20:00"),  # starts right after teardown: free
    ]
    result = _parse_search_payloads(
        *_payloads(rooms, bookings), "2026-11-03", "18:00", "19:00", TARGET
    )
    assert [r.name for r in result.rooms] == [
        "Price Center Study Room 1",
        "Price Center Study Room 3",
    ]


def test_unknown_reason_code_is_reported_verbatim():
    result = _parse_search_payloads(
        *_payloads([_room(1, 7)], []), "2026-11-03", "18:00", "19:00", TARGET
    )
    assert result.no_bookable_message() == (
        "Free but not bookable: Price Center Study Room 1 - EMS reason code 7."
    )


def test_reason_11_without_own_booking_shows_code():
    result = _parse_search_payloads(
        *_payloads([_room(1, 11)], []), "2026-11-03", "18:00", "19:00", TARGET
    )
    assert "EMS reason code 11" in result.no_bookable_message()


def test_no_free_rooms_message():
    result = SearchResult(rooms=[])
    assert result.no_bookable_message() == "No rooms available for the selected time."


def test_malformed_payload_raises():
    with pytest.raises(KeyError):
        _parse_search_payloads(
            {"d": "{}"}, {"d": "{}"}, "2026-11-03", "18:00", "19:00", TARGET
        )


# === _search fallback ===


def _run_search(monkeypatch, payloads, button_rooms, date="2026-11-03"):
    async def fake_retry(page, *args):
        return payloads

    async def fake_buttons(page, target_rooms):
        return [Room(name=n, available=True) for n in button_rooms]

    monkeypatch.setattr(booking, "_search_with_retry", fake_retry)
    monkeypatch.setattr(booking, "_parse_available_rooms", fake_buttons)
    return asyncio.run(booking._search(None, date, "18:00", "19:00", TARGET))


def test_search_uses_api_payloads(monkeypatch):
    result = _run_search(
        monkeypatch, _load("own_booking_day"), ["ignored"], date="2026-11-02"
    )
    assert result.detailed
    assert len(result.rooms) == 3


def test_search_falls_back_to_buttons(monkeypatch, capsys):
    result = _run_search(monkeypatch, None, ["Price Center Study Room 4"])
    assert not result.detailed
    assert [r.name for r in result.bookable_rooms] == ["Price Center Study Room 4"]
    assert "falling back" in capsys.readouterr().err


def test_search_fails_when_no_api_and_no_buttons(monkeypatch):
    with pytest.raises(BookingError, match="Could not determine room availability"):
        _run_search(monkeypatch, ({"d": "{}"}, {"d": "{}"}), [])
