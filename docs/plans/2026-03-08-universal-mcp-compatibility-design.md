# Universal MCP Compatibility Update

**Date:** 2026-03-08
**Status:** Approved

## Goal

Make ucsd-study-room universally usable across all MCP-compatible clients, not just Claude Code.

## Changes

### 1. MCP Server (`mcp_server.py`)
- Tool descriptions: Korean → English
- Response messages: Korean → English
- No logic changes

### 2. README.md Restructure
- Features: "Integrates with any MCP-compatible AI assistant" (no specific product names)
- "Getting Started with Claude Code" → generic "MCP Server Setup" section
- Compatible clients table:

| Client | Type | Config |
|--------|------|--------|
| Claude Code / Codex CLI / Gemini CLI | CLI | Each CLI's config file |
| Claude Desktop / Codex Desktop | Desktop App | Each app's config file |
| Cursor / Windsurf / Antigravity / Cline | IDE | Each IDE's MCP settings |

- CLI section: unchanged

### 3. pyproject.toml
- description: mention MCP server first
- keywords: add "ai", "llm"

### 4. README.ko.md
- Korean version of README.md
- README.md top: `[한국어](README.ko.md)` link
- README.ko.md top: `[English](README.md)` link

### Not Changed
- Core logic (`auth.py`, `booking.py`, `config.py`, `cli.py`)
- Dependencies
- Tests
- License
