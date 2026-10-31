# study_room/mcp_server.py
import asyncio
import re

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from study_room.auth import LoginError
from study_room.auth import login as auth_login
from study_room.booking import (
    BookingError,
    DateUnavailableError,
    SessionExpiredError,
    book_room,
    cancel_reservation,
    my_events,
    search_rooms,
)
from study_room.updater import get_update_notice

server = Server("study-room")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_rooms",
            description="Search for available UCSD Price Center Study Rooms (Rooms 1-8) by date and time range.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "start_time": {
                        "type": "string",
                        "description": "Start time (HH:MM, 24h)",
                    },
                    "end_time": {
                        "type": "string",
                        "description": "End time (HH:MM, 24h)",
                    },
                },
                "required": ["date", "start_time", "end_time"],
            },
        ),
        Tool(
            name="book_room",
            description="Book a specific study room. Use search_rooms first to find available rooms.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "start_time": {
                        "type": "string",
                        "description": "Start time (HH:MM)",
                    },
                    "end_time": {"type": "string", "description": "End time (HH:MM)"},
                    "room_name": {
                        "type": "string",
                        "description": "Room name (e.g. Price Center Study Room 2)",
                    },
                },
                "required": ["date", "start_time", "end_time", "room_name"],
            },
        ),
        Tool(
            name="my_events",
            description="List current reservations. Returns upcoming bookings with date, time, room, status, and reservation ID.",
            inputSchema={
                "type": "object",
                "properties": {},
                "required": [],
            },
        ),
        Tool(
            name="cancel_reservation",
            description=(
                "Cancel a study room reservation. Requires reason plus either "
                "reservation_id (preferred, from my_events) or date. "
                "Ask the user to choose a cancel reason before calling. "
                "Valid reasons: Bad Weather, Changed Date, Changed Location, "
                "Lack of Funding, Lack of Interest, Lack of Resources, "
                "Lack of Time to Plan, Other. "
                "If multiple reservations match, call again with reservation_id."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "reservation_id": {
                        "type": "string",
                        "description": "Exact reservation ID from my_events (preferred)",
                    },
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "reason": {
                        "type": "string",
                        "description": "Cancel reason. Must be one of: Bad Weather, Changed Date, Changed Location, Lack of Funding, Lack of Interest, Lack of Resources, Lack of Time to Plan, Other",
                    },
                    "room_name": {
                        "type": "string",
                        "description": "Exact room name to narrow a date match (optional)",
                    },
                },
                "required": ["reason"],
            },
        ),
        Tool(
            name="login",
            description=(
                "Authenticate via UCSD SSO + Duo Push. "
                "Use when session is expired. "
                "Runs headlessly with no visible window "
                "and can take up to ~90 seconds. "
                "Before calling, tell the user that login is starting, "
                "that it may take a minute, "
                "and to approve the Duo Push on their phone."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "username": {"type": "string", "description": "UCSD username"},
                    "password": {"type": "string", "description": "UCSD password"},
                },
                "required": ["username", "password"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    results = await _handle_tool(name, arguments)

    try:
        notice = get_update_notice()
        if notice:
            results.append(TextContent(type="text", text=f"⚠ {notice}"))
    except Exception:
        pass

    return results


async def _handle_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "search_rooms":
            rooms = await search_rooms(
                arguments["date"], arguments["start_time"], arguments["end_time"]
            )
            if not rooms:
                return [
                    TextContent(
                        type="text", text="No rooms available for the given time."
                    )
                ]
            lines = [f"{len(rooms)} room(s) available:"]
            for i, r in enumerate(rooms, 1):
                lines.append(f"  {i}. {r.name}")
            lines.append("\nUse the book_room tool to reserve a room.")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "book_room":
            result = await book_room(
                arguments["date"],
                arguments["start_time"],
                arguments["end_time"],
                arguments["room_name"],
            )
            return [TextContent(type="text", text=result)]

        elif name == "my_events":
            reservations = await my_events()
            if not reservations:
                return [TextContent(type="text", text="No current reservations.")]
            lines = [f"{len(reservations)} reservation(s):"]
            for r in reservations:
                lines.append(
                    f"  - {r.date} {r.time} | {r.room} | {r.status} (ID: {r.reservation_id})"
                )
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "cancel_reservation":
            date = arguments.get("date") or ""
            reservation_id = arguments.get("reservation_id")
            if not reservation_id and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
                return [
                    TextContent(
                        type="text",
                        text="Provide reservation_id, or date in YYYY-MM-DD format.",
                    )
                ]
            result = await cancel_reservation(
                date,
                arguments.get("room_name"),
                arguments["reason"],
                reservation_id=reservation_id,
            )

            if result.status == "cancelled":
                return [TextContent(type="text", text=result.message)]
            elif result.status == "needs_selection":
                lines = [result.message]
                for r in result.reservations:
                    lines.append(f"  - {r.room} | {r.status} (ID: {r.reservation_id})")
                lines.append(
                    "\nCall cancel_reservation again with 'reservation_id' to specify which one."
                )
                return [TextContent(type="text", text="\n".join(lines))]
            else:
                return [TextContent(type="text", text=result.message)]

        elif name == "login":
            await auth_login(arguments["username"], arguments["password"])
            return [TextContent(type="text", text="Login successful. Session saved.")]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except LoginError as e:
        return [TextContent(type="text", text=f"Login failed: {e}")]
    except SessionExpiredError as e:
        return [
            TextContent(
                type="text",
                text=f"Session expired: {e}\nPlease use the login tool first.",
            )
        ]
    except DateUnavailableError as e:
        return [TextContent(type="text", text=str(e))]
    except BookingError as e:
        return [TextContent(type="text", text=f"Booking failed: {e}")]
    except Exception as e:
        # First line only: Playwright appends a call log that can echo filled values.
        first_line = str(e).splitlines()[0] if str(e) else ""
        return [
            TextContent(type="text", text=f"Error: {type(e).__name__}: {first_line}")
        ]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )


def main_sync():
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
