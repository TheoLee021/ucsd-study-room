# Universal MCP Compatibility Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make ucsd-study-room universally usable across all MCP-compatible clients by translating MCP messages to English and restructuring documentation.

**Architecture:** Text-only changes — translate MCP server strings, rewrite README for client-agnostic framing, add Korean README, update pyproject metadata. No logic changes.

**Tech Stack:** Python, Markdown

---

### Task 1: Translate MCP Server to English

**Files:**
- Modify: `study_room/mcp_server.py:1-112`

**Step 1: Update tool descriptions and input schema descriptions**

Replace all Korean strings in `list_tools()` with English equivalents:

```python
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
```

**Step 2: Update response messages in `call_tool()`**

Replace all Korean response strings:

| Original | Replacement |
|----------|-------------|
| `"해당 시간에 빈 방이 없습니다."` | `"No rooms available for the given time."` |
| `f"빈 방 {len(rooms)}개:"` | `f"{len(rooms)} room(s) available:"` |
| `"\nbook_room 도구로 원하는 방을 예약하세요."` | `"\nUse the book_room tool to reserve a room."` |
| `"로그인 성공! 세션이 저장되었습니다."` | `"Login successful. Session saved."` |
| `f"세션 만료: {e}\nlogin 도구로 먼저 로그인해주세요."` | `f"Session expired: {e}\nPlease use the login tool first."` |
| `f"예약 실패: {e}"` | `f"Booking failed: {e}"` |
| `f"오류 발생: {e}"` | `f"Error: {e}"` |

**Step 3: Verify no Korean strings remain**

Run: `grep -n '[가-힣]' study_room/mcp_server.py`
Expected: No output (no Korean characters found)

**Step 4: Commit**

```bash
git add study_room/mcp_server.py
git commit -m "feat: translate MCP server descriptions and responses to English"
```

---

### Task 2: Update pyproject.toml

**Files:**
- Modify: `pyproject.toml:1-11`

**Step 1: Update description and keywords**

Change description from:
```
"CLI & MCP tool to automatically search and book UCSD study rooms via EMS"
```
To:
```
"MCP server and CLI tool for automated UCSD study room booking via EMS"
```

Change keywords from:
```python
keywords = ["ucsd", "study-room", "ems", "booking", "playwright", "mcp"]
```
To:
```python
keywords = ["ucsd", "study-room", "ems", "booking", "playwright", "mcp", "ai", "llm"]
```

**Step 2: Commit**

```bash
git add pyproject.toml
git commit -m "feat: update description to lead with MCP, add ai/llm keywords"
```

---

### Task 3: Rewrite README.md

**Files:**
- Modify: `README.md` (full rewrite)

**Step 1: Write the new README.md**

Full content:

```markdown
# ucsd-study-room

[한국어](README.ko.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

An MCP server and CLI tool that automatically searches and books UCSD Price Center study rooms (Rooms 1--8) through the EMS Cloud booking system. Works with any MCP-compatible AI assistant.

## Features

- **MCP server** -- Integrates with any MCP-compatible AI assistant for natural language room booking
- **Headless browser automation** -- Searches and books rooms using Playwright with real Chrome, no browser window required
- **UCSD SSO + Duo Push authentication** -- Handles SAML-based single sign-on and Duo two-factor authentication
- **Session persistence** -- Saves browser sessions (cookies + localStorage) for reuse; credentials stored securely in the system keyring (macOS Keychain, Windows Credential Locker, or Linux SecretService)
- **Automatic re-authentication** -- When SSO expires, opens a headed browser for Duo Push re-verification without requiring you to re-enter credentials
- **CLI interface** -- Simple `study-room` command for searching and booking from the terminal

## Requirements

- Python 3.11 or later
- Google Chrome installed
- UCSD account with Duo Push enabled

### Platform Support

| Platform | Status | Notes |
|----------|--------|-------|
| macOS | Fully supported | Credentials stored in Keychain |
| Windows | Supported | Credentials stored in Windows Credential Locker |
| Linux | Supported | Requires `gnome-keyring` or `kwallet` for credential storage; falls back to manual login if unavailable. Run `playwright install --with-deps chromium` for system dependencies. |

## Installation

```bash
pip install ucsd-study-room
playwright install chromium
```

## Initial Setup

**1. Set your contact info (required before booking):**

```bash
study-room config --name "Your Name" --email "you@ucsd.edu"
```

**2. Log in with your UCSD credentials (first time only):**

```bash
study-room login
```

A Chrome window will open. Enter your UCSD SSO credentials when prompted, then approve the Duo Push notification on your phone. Your session and credentials are saved for future use.

## MCP Server Setup

The MCP server communicates over stdio and works with any MCP-compatible client. Add the following to your client's MCP configuration:

```json
{
  "study-room": {
    "command": "python",
    "args": ["-m", "study_room.mcp_server"]
  }
}
```

### Compatible Clients

| Client | Type | Config Location |
|--------|------|-----------------|
| Claude Code / Codex CLI / Gemini CLI | CLI | Each CLI's config file |
| Claude Desktop / Codex Desktop | Desktop App | Each app's settings |
| Cursor / Windsurf / Antigravity / Cline | IDE | Each IDE's MCP settings |

Once configured, you can use natural language to manage bookings:

- "Search for available study rooms tomorrow from 2pm to 4pm"
- "Book Price Center Study Room 3 on March 11 from 3pm to 5pm"
- "Are there any rooms open this Friday afternoon?"

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_rooms` | Search for available rooms by date and time range |
| `book_room` | Book a specific room (use after `search_rooms`) |
| `login` | Authenticate via UCSD SSO + Duo Push |

## CLI Usage

### Commands

| Command | Description |
|---------|-------------|
| `study-room login` | SSO login with Duo Push (opens browser for first-time auth) |
| `study-room search` | Search available rooms with `--date`, `--start`, `--end` options |
| `study-room search --book` | Search and book a room interactively |
| `study-room config` | View or set user info (`--name`, `--email`, `--attendees`) |
| `study-room status` | Check whether the current session is valid |

### Examples

**Search for available rooms:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00
```

**Search and book interactively:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00 --book
```

## How It Works

1. **Browser automation** -- Uses Playwright with real Chrome (`channel="chrome"`) in headless mode to interact with the EMS Cloud booking system.
2. **Authentication** -- Navigates to the UCSD SAML SSO page, submits credentials, and waits for Duo Push approval. On first login, a headed browser window opens for the Duo flow.
3. **Session management** -- After authentication, cookies and browser storage state are saved to `~/.study-room/`. Credentials are stored in the system keyring via the `keyring` library (macOS Keychain, Windows Credential Locker, or Linux SecretService). Sessions are valid for 7 days.
4. **Auto re-login** -- When a session expires during a search or booking operation, the tool automatically opens a headed browser, loads credentials from the system keyring, and re-authenticates with Duo Push.
5. **Room search** -- Navigates to the EMS booking page, fills in date and time fields, and parses available rooms by inspecting the DOM for booking buttons.
6. **Booking** -- Clicks the add-to-cart button for the selected room, fills in the reservation form (name, email, terms), and submits the reservation.

## Configuration

Configuration is stored in `~/.study-room/config.yaml`. Default target rooms are Price Center Study Room 1 through 8.

```yaml
name: "Your Name"
email: "you@ucsd.edu"
default_attendees: 1
rooms:
  - Price Center Study Room 1
  - Price Center Study Room 2
  - Price Center Study Room 3
  - Price Center Study Room 4
  - Price Center Study Room 5
  - Price Center Study Room 6
  - Price Center Study Room 7
  - Price Center Study Room 8
```

## Contributing

Contributions are welcome. To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Commit your changes
4. Push to the branch and open a pull request

Please make sure existing tests pass before submitting.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE) for details.
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: restructure README for universal MCP client compatibility"
```

---

### Task 4: Create README.ko.md

**Files:**
- Create: `README.ko.md`

**Step 1: Write Korean README**

Translate the new README.md into Korean, with `[English](README.md)` link at top.

Full content:

```markdown
# ucsd-study-room

[English](README.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

UCSD Price Center 스터디룸(1~8번)을 EMS Cloud 예약 시스템을 통해 자동으로 검색하고 예약하는 MCP 서버 및 CLI 도구입니다. MCP를 지원하는 모든 AI 어시스턴트에서 사용할 수 있습니다.

## 기능

- **MCP 서버** -- MCP 호환 AI 어시스턴트와 연동하여 자연어로 스터디룸 예약
- **헤드리스 브라우저 자동화** -- Playwright와 실제 Chrome을 사용하여 브라우저 창 없이 검색 및 예약
- **UCSD SSO + Duo Push 인증** -- SAML 기반 SSO 및 Duo 이중 인증 처리
- **세션 유지** -- 브라우저 세션(쿠키 + localStorage)을 저장하여 재사용; 자격 증명은 시스템 키링(macOS Keychain, Windows Credential Locker, Linux SecretService)에 안전하게 저장
- **자동 재인증** -- SSO 만료 시 자격 증명 재입력 없이 Duo Push 재인증을 위한 브라우저 자동 실행
- **CLI 인터페이스** -- 터미널에서 간단한 `study-room` 명령어로 검색 및 예약

## 요구 사항

- Python 3.11 이상
- Google Chrome 설치
- Duo Push가 활성화된 UCSD 계정

### 플랫폼 지원

| 플랫폼 | 상태 | 비고 |
|--------|------|------|
| macOS | 완전 지원 | Keychain에 자격 증명 저장 |
| Windows | 지원 | Windows Credential Locker에 저장 |
| Linux | 지원 | `gnome-keyring` 또는 `kwallet` 필요; 없으면 수동 로그인. `playwright install --with-deps chromium`으로 시스템 의존성 설치 |

## 설치

```bash
pip install ucsd-study-room
playwright install chromium
```

## 초기 설정

**1. 연락처 설정 (예약 전 필수):**

```bash
study-room config --name "이름" --email "you@ucsd.edu"
```

**2. UCSD 계정으로 로그인 (최초 1회):**

```bash
study-room login
```

Chrome 창이 열립니다. UCSD SSO 자격 증명을 입력하고, 휴대폰에서 Duo Push 알림을 승인하세요. 세션과 자격 증명이 저장됩니다.

## MCP 서버 설정

MCP 서버는 stdio로 통신하며, MCP를 지원하는 모든 클라이언트에서 사용할 수 있습니다. 클라이언트의 MCP 설정에 다음을 추가하세요:

```json
{
  "study-room": {
    "command": "python",
    "args": ["-m", "study_room.mcp_server"]
  }
}
```

### 호환 클라이언트

| 클라이언트 | 유형 | 설정 위치 |
|-----------|------|----------|
| Claude Code / Codex CLI / Gemini CLI | CLI | 각 CLI의 설정 파일 |
| Claude Desktop / Codex Desktop | Desktop App | 각 앱의 설정 |
| Cursor / Windsurf / Antigravity / Cline | IDE | 각 IDE의 MCP 설정 |

설정 완료 후 자연어로 예약을 관리할 수 있습니다:

- "내일 오후 2시부터 4시까지 빈 스터디룸 검색해줘"
- "3월 11일 오후 3시부터 5시까지 Price Center Study Room 3 예약해줘"
- "이번 금요일 오후에 빈 방 있어?"

### MCP 도구

| 도구 | 설명 |
|------|------|
| `search_rooms` | 날짜와 시간 범위로 빈 방 검색 |
| `book_room` | 특정 방 예약 (`search_rooms` 후 사용) |
| `login` | UCSD SSO + Duo Push 인증 |

## CLI 사용법

### 명령어

| 명령어 | 설명 |
|--------|------|
| `study-room login` | SSO 로그인 + Duo Push (최초 인증 시 브라우저 실행) |
| `study-room search` | `--date`, `--start`, `--end` 옵션으로 빈 방 검색 |
| `study-room search --book` | 검색 후 대화형으로 예약 |
| `study-room config` | 사용자 정보 확인/설정 (`--name`, `--email`, `--attendees`) |
| `study-room status` | 현재 세션 유효 여부 확인 |

### 예시

**빈 방 검색:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00
```

**검색 후 예약:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00 --book
```

## 작동 방식

1. **브라우저 자동화** -- Playwright와 실제 Chrome(`channel="chrome"`)을 헤드리스 모드로 사용하여 EMS Cloud 예약 시스템과 상호작용
2. **인증** -- UCSD SAML SSO 페이지로 이동, 자격 증명 입력, Duo Push 승인 대기. 최초 로그인 시 Duo 흐름을 위해 브라우저 창이 열림
3. **세션 관리** -- 인증 후 쿠키와 브라우저 저장 상태를 `~/.study-room/`에 저장. `keyring` 라이브러리를 통해 시스템 키링에 자격 증명 저장. 세션 유효 기간 7일
4. **자동 재로그인** -- 검색/예약 중 세션 만료 시 자동으로 브라우저를 열고, 시스템 키링에서 자격 증명을 로드하여 Duo Push로 재인증
5. **방 검색** -- EMS 예약 페이지로 이동, 날짜와 시간 입력, DOM에서 예약 버튼을 검사하여 빈 방 파싱
6. **예약** -- 선택한 방의 장바구니 버튼 클릭, 예약 양식(이름, 이메일, 약관) 작성 후 제출

## 설정

설정은 `~/.study-room/config.yaml`에 저장됩니다. 기본 대상은 Price Center Study Room 1~8입니다.

```yaml
name: "이름"
email: "you@ucsd.edu"
default_attendees: 1
rooms:
  - Price Center Study Room 1
  - Price Center Study Room 2
  - Price Center Study Room 3
  - Price Center Study Room 4
  - Price Center Study Room 5
  - Price Center Study Room 6
  - Price Center Study Room 7
  - Price Center Study Room 8
```

## 기여

기여를 환영합니다:

1. 저장소를 포크합니다
2. 기능 브랜치를 만듭니다 (`git checkout -b feature/your-feature`)
3. 변경 사항을 커밋합니다
4. 브랜치에 푸시하고 Pull Request를 엽니다

제출 전 기존 테스트가 통과하는지 확인해 주세요.

## 라이선스

이 프로젝트는 MIT 라이선스로 배포됩니다. 자세한 내용은 [LICENSE](LICENSE)를 참조하세요.
```

**Step 2: Commit**

```bash
git add README.ko.md
git commit -m "docs: add Korean README (README.ko.md)"
```
