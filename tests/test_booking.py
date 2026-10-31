from study_room.booking import CANCEL_REASONS, CancelResult, Reservation


def test_cancel_reasons_has_8_options():
    assert len(CANCEL_REASONS) == 8


def test_cancel_reasons_contains_expected_values():
    assert "Bad Weather" in CANCEL_REASONS
    assert "Changed Date" in CANCEL_REASONS
    assert "Other" in CANCEL_REASONS


def test_cancel_result_cancelled():
    result = CancelResult(status="cancelled", message="Cancelled: Room 1")
    assert result.status == "cancelled"
    assert result.reservations is None


def test_cancel_result_needs_selection():
    reservations = [
        Reservation(
            date="Mar 12",
            time="3:00 PM - 5:00 PM",
            room="Room 1",
            status="Confirmed",
            reservation_id="123",
        ),
        Reservation(
            date="Mar 12",
            time="5:00 PM - 7:00 PM",
            room="Room 2",
            status="Confirmed",
            reservation_id="456",
        ),
    ]
    result = CancelResult(
        status="needs_selection",
        message="Multiple reservations found",
        reservations=reservations,
    )
    assert result.status == "needs_selection"
    assert len(result.reservations) == 2


def test_cancel_result_error():
    result = CancelResult(status="error", message="No reservation found")
    assert result.status == "error"


def _row(index, rid, date="Mar 13, 2026", room="Price Center Study Room 2"):
    return {
        "index": index,
        "reservation": Reservation(
            date=date, time="", room=room, status="Confirmed", reservation_id=rid
        ),
    }


def test_select_cancel_target_by_reservation_id_picks_exact_row():
    from study_room.booking import _select_cancel_target

    rows = [_row(0, "1001"), _row(1, "1002")]
    target, early = _select_cancel_target(
        rows, "Mar 13, 2026", "Price Center Study Room 2", "1002"
    )
    assert early is None
    assert target["reservation"].reservation_id == "1002"


def test_select_cancel_target_same_room_same_day_needs_selection():
    from study_room.booking import _select_cancel_target

    rows = [_row(0, "1001"), _row(1, "1002")]
    target, early = _select_cancel_target(
        rows, "Mar 13, 2026", "Price Center Study Room 2", None
    )
    assert target is None
    assert early.status == "needs_selection"
    assert [r.reservation_id for r in early.reservations] == ["1001", "1002"]


def test_select_cancel_target_room_must_match_exactly():
    from study_room.booking import _select_cancel_target

    rows = [_row(0, "1001", room="Price Center Study Room 2")]
    target, early = _select_cancel_target(rows, "Mar 13, 2026", "Room", None)
    assert target is None
    assert early.status == "error"


def test_select_cancel_target_unknown_id_is_error():
    from study_room.booking import _select_cancel_target

    target, early = _select_cancel_target([_row(0, "1001")], "", None, "9999")
    assert target is None
    assert early.status == "error"


def test_cancel_reservation_rejects_invalid_reason():
    import asyncio

    from study_room.booking import cancel_reservation

    result = asyncio.run(cancel_reservation("2026-03-13", reason="Because"))
    assert result.status == "error"
