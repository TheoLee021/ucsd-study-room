from study_room.booking import CancelResult, CANCEL_REASONS, Reservation


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
        Reservation(date="Mar 12", time="3:00 PM - 5:00 PM", room="Room 1", status="Confirmed", reservation_id="123"),
        Reservation(date="Mar 12", time="5:00 PM - 7:00 PM", room="Room 2", status="Confirmed", reservation_id="456"),
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
