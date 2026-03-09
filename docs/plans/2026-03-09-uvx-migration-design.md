# uvx Migration Design

## Problem

1. `pip install ucsd-study-room`은 글로벌 Python에 설치되어 Python 업그레이드 시 깨짐
2. MCP 설정의 `"command": "python"`이 어떤 Python을 가리키는지 보장 안 됨
3. MCP 서버용 entry point가 없어 `uvx`로 직접 실행 불가

## Solution

`uvx` 기반으로 전환. MCP 생태계 표준에 맞춤.

## Changes

### 1. pyproject.toml

- `study-room-mcp` entry point 추가
- 버전 0.1.0 → 0.2.0

```toml
[project.scripts]
study-room = "study_room.cli:app"
study-room-mcp = "study_room.mcp_server:main_sync"
```

### 2. mcp_server.py

`main_sync()` 동기 래퍼 추가 (entry point는 동기 함수 필요):

```python
def main_sync():
    asyncio.run(main())
```

### 3. README.md

Quick Start, Manual Installation, MCP Server Setup을 uvx 기반으로 변경.
pip 방식은 fallback으로 유지.

**Quick Start:**
```
1. Run: uv tool install ucsd-study-room && uvx --from ucsd-study-room playwright install chromium
2. Add "study-room" to your MCP config: {"command": "uvx", "args": ["--from", "ucsd-study-room", "study-room-mcp"]}
3. Run: study-room config --name "MY NAME" --email "MY_EMAIL@ucsd.edu"
4. Run: study-room login
```

**MCP config:**
```json
{
  "study-room": {
    "command": "uvx",
    "args": ["--from", "ucsd-study-room", "study-room-mcp"]
  }
}
```

### 4. 개발용 CLAUDE.md

MCP 설정 예시를 uvx 기반으로 업데이트.

## Version

0.1.0 → 0.2.0 (entry point 추가 = 기능 추가)
