# My Events (Reservation Lookup) Design

**Date:** 2026-03-08
**Status:** Approved

## Goal

Add ability to view current reservations from the EMS MY EVENTS page.

## Scope

- Parse CURRENT tab of `BrowseReservations.aspx`
- Return fields: date, room name, status, reservation ID

## Data Model

```python
@dataclass
class Reservation:
    date: str          # "Mon Mar 9, 2026"
    room: str          # "Price Center Study Room 3"
    status: str        # "Confirmed"
    reservation_id: str # "317584"
```

## Changes

| File | Change |
|------|--------|
| `booking.py` | Add `my_events()` — navigate to MY EVENTS, parse DOM table |
| `cli.py` | Add `study-room events` command |
| `mcp_server.py` | Add `my_events` MCP tool |
| `README.md` | Add to CLI commands table + MCP tools table |
| `README.ko.md` | Same |

## Flow

1. Open authenticated headless browser
2. Navigate to EMS home, click MY EVENTS
3. Wait for CURRENT tab table to load
4. Parse each row: date, location (room name), status, ID
5. Return `list[Reservation]`

## Not Changed

- auth.py (reuse existing auth flow)
- config.py
