# study_room/mcp_server.py
import asyncio
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from study_room.booking import (
    search_rooms,
    book_room,
    SessionExpiredError,
    DateUnavailableError,
    BookingError,
)
from study_room.auth import login as auth_login, is_session_valid

server = Server("study-room")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="search_rooms",
            description="UCSD Price Center Study Room 1~8에서 빈 방을 검색한다.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "날짜 (YYYY-MM-DD)"},
                    "start_time": {"type": "string", "description": "시작 시간 (HH:MM, 24h)"},
                    "end_time": {"type": "string", "description": "종료 시간 (HH:MM, 24h)"},
                },
                "required": ["date", "start_time", "end_time"],
            },
        ),
        Tool(
            name="book_room",
            description="특정 스터디룸을 예약한다. search_rooms로 먼저 빈 방을 확인한 뒤 사용.",
            inputSchema={
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "날짜 (YYYY-MM-DD)"},
                    "start_time": {"type": "string", "description": "시작 시간 (HH:MM)"},
                    "end_time": {"type": "string", "description": "종료 시간 (HH:MM)"},
                    "room_name": {"type": "string", "description": "방 이름 (예: Price Center Study Room 2)"},
                },
                "required": ["date", "start_time", "end_time", "room_name"],
            },
        ),
        Tool(
            name="login",
            description="UCSD SSO + Duo Push 로그인. 세션 만료 시 사용. 브라우저가 열리고 Duo 승인이 필요.",
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
    try:
        if name == "search_rooms":
            rooms = await search_rooms(
                arguments["date"], arguments["start_time"], arguments["end_time"]
            )
            if not rooms:
                return [TextContent(type="text", text="해당 시간에 빈 방이 없습니다.")]
            lines = [f"빈 방 {len(rooms)}개:"]
            for i, r in enumerate(rooms, 1):
                lines.append(f"  {i}. {r.name}")
            lines.append("\nbook_room 도구로 원하는 방을 예약하세요.")
            return [TextContent(type="text", text="\n".join(lines))]

        elif name == "book_room":
            result = await book_room(
                arguments["date"],
                arguments["start_time"],
                arguments["end_time"],
                arguments["room_name"],
            )
            return [TextContent(type="text", text=result)]

        elif name == "login":
            await auth_login(arguments["username"], arguments["password"])
            return [TextContent(type="text", text="로그인 성공! 세션이 저장되었습니다.")]

        else:
            return [TextContent(type="text", text=f"Unknown tool: {name}")]

    except SessionExpiredError as e:
        return [TextContent(type="text", text=f"세션 만료: {e}\nlogin 도구로 먼저 로그인해주세요.")]
    except DateUnavailableError as e:
        return [TextContent(type="text", text=str(e))]
    except BookingError as e:
        return [TextContent(type="text", text=f"예약 실패: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"오류 발생: {e}")]


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
