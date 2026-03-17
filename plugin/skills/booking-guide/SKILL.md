---
name: booking-guide
description: Use when the user wants to book, cancel, or check UCSD study room reservations. Trigger on "study room", "방 예약", "예약 취소", "스터디룸", "Price Center", or any room booking intent.
---

# UCSD Study Room Booking Guide

You have access to MCP tools for managing UCSD Price Center Study Room reservations.

## Available Tools

- `search_rooms(date, start_time, end_time)` — Search available rooms
- `book_room(date, start_time, end_time, room_name)` — Book a specific room
- `my_events()` — List current reservations
- `cancel_reservation(date, reason, room_name?)` — Cancel a reservation
- `login(username, password)` — Authenticate (UCSD SSO + Duo Push)

## Booking Flow

1. Confirm date and time with the user (date: `YYYY-MM-DD`, time: `HH:MM` 24h format)
2. Call `search_rooms` to find available rooms
3. Present the available rooms and ask the user which one to book
4. Call `book_room` with the selected room name (exact match required, e.g., "Price Center Study Room 3")

## Cancellation Flow

1. Call `my_events` to show current reservations
2. Ask the user which reservation to cancel and why
3. Reason MUST be one of: Bad Weather, Changed Date, Changed Location, Lack of Funding, Lack of Interest, Lack of Resources, Lack of Time to Plan, Other
4. Call `cancel_reservation` with date, reason, and optionally room_name

## Error Handling

- If a tool returns "Session expired", call `login` first, then retry
- Rooms are Price Center Study Room 1 through 8
- Maximum 4 hours per booking per day
