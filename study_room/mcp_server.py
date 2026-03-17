# study_room/mcp_server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from study_room.booking import (
    search_rooms,
    book_room,
    my_events,
    cancel_reservation,
    CANCEL_REASONS,
    SessionExpiredError,
    DateUnavailableError,
    BookingError,
)
from study_room.auth import login as auth_login, is_session_valid
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
                    "start_time": {"type": "string", "description": "Start time (HH:MM, 24h)"},
                    "end_time": {"type": "string", "description": "End time (HH:MM, 24h)"},
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
                    "start_time": {"type": "string", "description": "Start time (HH:MM)"},
                    "end_time": {"type": "string", "description": "End time (HH:MM)"},
                    "room_name": {"type": "string", "description": "Room name (e.g. Price Center Study Room 2)"},
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
                "Cancel a study room reservation. Requires date and reason. "
                "Ask the user to choose a cancel reason before calling. "
                "Valid reasons: Bad Weather, Changed Date, Changed Location, "
                "Lack of Funding, Lack of Interest, Lack of Resources, "
                "Lack of Time to Plan, Other. "
                "If multiple reservations on the same date, specify room_name."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "Date (YYYY-MM-DD)"},
                    "reason": {
                        "type": "string",
                        "description": "Cancel reason. Must be one of: Bad Weather, Changed Date, Changed Location, Lack of Funding, Lack of Interest, Lack of Resources, Lack of Time to Plan, Other",
                    },
                    "room_name": {"type": "string", "description": "Room name to disambiguate if multiple reservations on same date (optional)"},
                },
                "required": ["date", "reason"],
            },
        ),
        Tool(
            name="login",
            description="Authenticate via UCSD SSO + Duo Push. Use when session is expired. Opens a browser and requires Duo approval.",
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
                return [TextContent(type="text", text="No rooms available for the given time.")]
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
                lines.append(f"  - {r.date} {r.time} | {r.room} | {r.status} (ID: {r.reservation_id})")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "cancel_reservation":
            result = await cancel_reservation(
                arguments["date"],
                arguments.get("room_name"),
                arguments["reason"],
            )

            if result.status == "cancelled":
                return [TextContent(type="text", text=result.message)]
            elif result.status == "needs_selection":
                lines = [result.message]
                for r in result.reservations:
                    lines.append(f"  - {r.room} | {r.status} (ID: {r.reservation_id})")
                lines.append("\nCall cancel_reservation again with 'room_name' to specify which one.")
                return [TextContent(type="text", text="\n".join(lines))]
            else:
                return [TextContent(type="text", text=result.message)]

        elif name == "login":
            await auth_login(arguments["username"], arguments["password"])
            return [TextContent(type="text", text="Login successful. Session saved.")]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except SessionExpiredError as e:
        return [TextContent(type="text", text=f"Session expired: {e}\nPlease use the login tool first.")]
    except DateUnavailableError as e:
        return [TextContent(type="text", text=str(e))]
    except BookingError as e:
        return [TextContent(type="text", text=f"Booking failed: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def main_sync():
    asyncio.run(main())


if __name__ == "__main__":
    main_sync()
