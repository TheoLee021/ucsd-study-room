# ucsd-study-room

## 교훈
- PyPI + setuptools: `license = "MIT"` 사용 시 classifiers에서 License classifier 제거 필요 (PEP 639)

## 배포 구조

2-track 배포:

**Track 1: CLI (PyPI)**
- 설치: `uv tool install ucsd-study-room`
- 업데이트: `study-room update`
- 버전 알림: CLI 실행 후 stderr에 표시, MCP 응답에 TextContent로 추가
- 캐시: `~/.study-room/update_check.json` (하루 1회 PyPI 체크)

**Track 2: Claude Code Plugin**
- 3개 repo 분리 구조:
  - `ucsd-study-room` — Python 코드 (PyPI 배포)
  - `ucsd-study-room-plugin` — 플러그인 파일 (.claude-plugin/, .mcp.json, skills/)
  - `claude-plugins` — 마켓플레이스 (marketplace.json)
- Python 코드 업데이트: `uvx --refresh`가 PyPI 최신 버전 자동 다운로드
- 스킬/설정 업데이트: plugin repo push + marketplace 버전 올리면 자동

Python 코드 변경 시 PyPI만 배포. 스킬/MCP 설정 변경 시 plugin repo push + marketplace 버전 올리기.
