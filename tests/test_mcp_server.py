import asyncio
import threading

from mcp.types import TextContent

import study_room.mcp_server as mcp_server


async def _fake_handle_tool(name, arguments):
    return [TextContent(type="text", text="ok")]


def test_call_tool_respects_no_update_check(monkeypatch):
    monkeypatch.setenv("STUDY_ROOM_NO_UPDATE_CHECK", "1")
    monkeypatch.setattr(mcp_server, "_handle_tool", _fake_handle_tool)

    def fail():
        raise AssertionError("update check should be skipped")

    monkeypatch.setattr(mcp_server, "get_update_notice", fail)
    results = asyncio.run(mcp_server.call_tool("my_events", {}))
    assert [r.text for r in results] == ["ok"]


def test_call_tool_runs_update_check_off_event_loop(monkeypatch):
    monkeypatch.delenv("STUDY_ROOM_NO_UPDATE_CHECK", raising=False)
    monkeypatch.setattr(mcp_server, "_handle_tool", _fake_handle_tool)
    main_thread = threading.get_ident()
    seen = {}

    def notice():
        seen["thread"] = threading.get_ident()
        return "New version available"

    monkeypatch.setattr(mcp_server, "get_update_notice", notice)
    results = asyncio.run(mcp_server.call_tool("my_events", {}))
    assert seen["thread"] != main_thread
    assert results[-1].text == "⚠ New version available"
