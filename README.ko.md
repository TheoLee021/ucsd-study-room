# ucsd-study-room

[English](README.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

AI 어시스턴트 또는 터미널에서 UCSD Price Center 스터디룸 예약을 자동화합니다.

**가능한 기능:**

- **검색** -- 날짜와 시간으로 빈 방 검색
- **예약** -- 즉시 방 예약
- **취소** -- 사유를 선택하여 예약 취소
- **조회** -- 현재 예약 목록 확인

Claude Code, Codex CLI, Gemini CLI, Cursor 등 MCP 호환 클라이언트에서 사용할 수 있습니다.

## 빠른 시작

MCP를 지원하는 AI 어시스턴트(Claude Code, Codex CLI 등)를 사용 중이라면, 아래 프롬프트를 복사해서 붙여넣기만 하세요:

```
ucsd-study-room MCP 서버를 설치해줘:
1. 실행: uv tool install ucsd-study-room && uvx --from ucsd-study-room playwright install chromium
2. MCP 설정에 "study-room" 추가: {"command": "uvx", "args": ["--from", "ucsd-study-room", "study-room-mcp"]}
3. 실행: study-room config --name "내 이름" --email "MY_EMAIL@ucsd.edu"
4. 실행: study-room login
```

`내 이름`과 `MY_EMAIL@ucsd.edu`를 본인의 이름과 UCSD 이메일로 바꾼 뒤 붙여넣으세요. AI 어시스턴트가 나머지를 처리합니다.

설정이 끝나면 AI 어시스턴트에게 자연어로 요청하세요:

- "내일 오후 2시부터 4시까지 빈 스터디룸 검색해줘"
- "3월 11일 오후 3시부터 5시까지 Price Center Study Room 예약해줘"
- "3월 13일 예약 취소해줘"
- "내 예약 목록 보여줘"

## 요구 사항

- Python 3.11 이상
- Google Chrome 설치
- Duo Push가 활성화된 UCSD 계정

### 플랫폼 지원

| 플랫폼     | 상태    | 비고                                                                                                  |
| ------- | ----- | --------------------------------------------------------------------------------------------------- |
| macOS   | 완전 지원 | Keychain에 자격 증명 저장                                                                                  |
| Windows | 지원    | Windows Credential Locker에 저장                                                                       |
| Linux   | 지원    | `gnome-keyring` 또는 `kwallet` 필요; 없으면 수동 로그인. `playwright install --with-deps chromium`으로 시스템 의존성 설치 |

## 수동 설치

```bash
uv tool install ucsd-study-room
uvx --from ucsd-study-room playwright install chromium
```

<details>
<summary>대안: pip install</summary>

```bash
pip install ucsd-study-room
playwright install chromium
```

pip를 사용하는 경우, MCP 서버를 다음과 같이 설정하세요:

```json
{
  "study-room": {
    "command": "study-room-mcp"
  }
}
```

</details>

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
    "command": "uvx",
    "args": ["--from", "ucsd-study-room", "study-room-mcp"]
  }
}
```

### 호환 클라이언트

| 클라이언트                                   | 유형          | 설정 위치         |
| --------------------------------------- | ----------- | ------------- |
| Claude Code / Codex CLI / Gemini CLI    | CLI         | 각 CLI의 설정 파일  |
| Claude Desktop / Codex Desktop          | Desktop App | 각 앱의 설정       |
| Cursor / Windsurf / Antigravity / Cline | IDE         | 각 IDE의 MCP 설정 |

설정 완료 후 자연어로 예약을 관리할 수 있습니다:

- "내일 오후 2시부터 4시까지 빈 스터디룸 검색해줘"
- "3월 11일 오후 3시부터 5시까지 Price Center Study Room 3 예약해줘"
- "3월 13일 예약 취소해줘"
- "이번 금요일 오후에 빈 방 있어?"

### MCP 도구

| 도구                     | 설명                            |
| ---------------------- | ----------------------------- |
| `search_rooms`         | 날짜와 시간 범위로 빈 방 검색             |
| `book_room`            | 특정 방 예약 (`search_rooms` 후 사용) |
| `cancel_reservation`   | 날짜와 사유로 예약 취소                 |
| `my_events`            | 현재 예약 목록 조회 (날짜, 방, 상태, ID)   |
| `login`                | UCSD SSO + Duo Push 인증        |

## CLI 사용법

### 명령어

| 명령어                        | 설명                                                |
| -------------------------- | ------------------------------------------------- |
| `study-room login`         | SSO 로그인 + Duo Push (최초 인증 시 브라우저 실행)              |
| `study-room search`        | `--date`, `--start`, `--end` 옵션으로 빈 방 검색          |
| `study-room search --book` | 검색 후 대화형으로 예약                                     |
| `study-room cancel`        | 대화형 또는 `--date`, `--reason` 옵션으로 예약 취소            |
| `study-room events`        | 현재 예약 목록 조회                                       |
| `study-room config`        | 사용자 정보 확인/설정 (`--name`, `--email`, `--attendees`) |
| `study-room status`        | 현재 세션 유효 여부 확인                                    |

### 예시

**빈 방 검색:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00
```

**검색 후 예약:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00 --book
```

**예약 취소:**

```bash
study-room cancel                              # 대화형 선택
study-room cancel --date 2026-03-13            # 날짜 지정 (사유 선택 프롬프트)
study-room cancel --date 2026-03-13 --reason "Changed Date"
```

## 작동 방식

1. **브라우저 자동화** -- Playwright와 실제 Chrome(`channel="chrome"`)을 헤드리스 모드로 사용하여 EMS Cloud 예약 시스템과 상호작용
2. **인증** -- UCSD SAML SSO 페이지로 이동, 자격 증명 입력, Duo Push 승인 대기. 최초 로그인 시 Duo 흐름을 위해 브라우저 창이 열림
3. **세션 관리** -- 인증 후 쿠키와 브라우저 저장 상태를 `~/.study-room/`에 저장. `keyring` 라이브러리를 통해 시스템 키링에 자격 증명 저장. 세션 유효 기간 7일
4. **자동 재로그인** -- 검색/예약 중 세션 만료 시 자동으로 브라우저를 열고, 시스템 키링에서 자격 증명을 로드하여 Duo Push로 재인증
5. **방 검색** -- EMS 예약 페이지로 이동, 날짜와 시간 입력, DOM에서 예약 버튼을 검사하여 빈 방 파싱
6. **예약** -- 선택한 방의 장바구니 버튼 클릭, 예약 양식(이름, 이메일, 약관) 작성 후 제출
7. **취소** -- My Events로 이동, 예약 링크 클릭, 취소 사유 드롭다운 선택 후 취소 확인

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
