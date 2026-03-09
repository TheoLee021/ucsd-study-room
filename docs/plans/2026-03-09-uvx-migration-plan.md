# uvx Migration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add MCP server entry point and migrate installation/config docs from pip to uvx

**Architecture:** Add `study-room-mcp` console_scripts entry point pointing to a sync wrapper around the existing async `main()`. Update all README installation and MCP config sections to use uvx. Bump version to 0.2.0.

**Tech Stack:** Python setuptools (entry points), uvx, PyPI

---

### Task 1: Add MCP server entry point

**Files:**
- Modify: `study_room/mcp_server.py:124-130`
- Modify: `pyproject.toml:2,35-36`

**Step 1: Add `main_sync()` wrapper to mcp_server.py**

Add before `if __name__`:

```python
def main_sync():
    asyncio.run(main())
```

Update `if __name__` block to use it:

```python
if __name__ == "__main__":
    main_sync()
```

**Step 2: Add entry point to pyproject.toml**

```toml
[project.scripts]
study-room = "study_room.cli:app"
study-room-mcp = "study_room.mcp_server:main_sync"
```

**Step 3: Bump version**

```toml
version = "0.2.0"
```

**Step 4: Verify entry point works locally**

Run:
```bash
cd /Users/theo/Documents/GitHub/ucsd-study-room
.venv/bin/pip install -e .
```

Verify `study-room-mcp` executable exists:
```bash
ls .venv/bin/study-room-mcp
```
Expected: file exists

**Step 5: Commit**

```bash
git add study_room/mcp_server.py pyproject.toml
git commit -m "feat: add study-room-mcp entry point for uvx support"
```

---

### Task 2: Update README Quick Start

**Files:**
- Modify: `README.md:33-45` (Quick Start section)

**Step 1: Replace Quick Start prompt block**

Before:
```
Install the ucsd-study-room MCP server:
1. Run: pip install ucsd-study-room && playwright install chromium
2. Add "study-room" to your MCP config: {"command": "python", "args": ["-m", "study_room.mcp_server"]}
3. Run: study-room config --name "MY NAME" --email "MY_EMAIL@ucsd.edu"
4. Run: study-room login
```

After:
```
Install the ucsd-study-room MCP server:
1. Run: uv tool install ucsd-study-room && uvx --from ucsd-study-room playwright install chromium
2. Add "study-room" to your MCP config: {"command": "uvx", "args": ["--from", "ucsd-study-room", "study-room-mcp"]}
3. Run: study-room config --name "MY NAME" --email "MY_EMAIL@ucsd.edu"
4. Run: study-room login
```

**Step 2: Commit**

```bash
git add README.md
git commit -m "docs: update Quick Start to uvx"
```

---

### Task 3: Update README Manual Installation + MCP Server Setup

**Files:**
- Modify: `README.md:53-58` (Manual Installation)
- Modify: `README.md:78-87` (MCP Server Setup)

**Step 1: Replace Manual Installation**

Before:
```bash
pip install ucsd-study-room
playwright install chromium
```

After:
```bash
uv tool install ucsd-study-room
uvx --from ucsd-study-room playwright install chromium
```

Add a pip fallback note after:
```markdown
<details>
<summary>Alternative: pip install</summary>

```bash
pip install ucsd-study-room
playwright install chromium
```

If using pip, configure the MCP server with:
```json
{
  "study-room": {
    "command": "study-room-mcp"
  }
}
```

</details>
```

**Step 2: Replace MCP Server Setup config**

Before:
```json
{
  "study-room": {
    "command": "python",
    "args": ["-m", "study_room.mcp_server"]
  }
}
```

After:
```json
{
  "study-room": {
    "command": "uvx",
    "args": ["--from", "ucsd-study-room", "study-room-mcp"]
  }
}
```

**Step 3: Commit**

```bash
git add README.md
git commit -m "docs: update installation and MCP setup to uvx"
```

---

### Task 4: Update README.ko.md

**Files:**
- Modify: `README.ko.md`

**Step 1: Apply same changes as Task 2-3 to Korean README**

Mirror all Quick Start, Manual Installation, MCP Server Setup changes.

**Step 2: Commit**

```bash
git add README.ko.md
git commit -m "docs: update Korean README to uvx"
```

---

### Task 5: Update dev CLAUDE.md MCP config

**Files:**
- Modify: `/Users/theo/Documents/ClaudeCode/study-room-booking/CLAUDE.md:136-148`

**Step 1: Replace MCP server config example**

Before:
```json
{
  "mcpServers": {
    "study-room": {
      "command": "python",
      "args": ["-m", "study_room.mcp_server"]
    }
  }
}
```

After:
```json
{
  "mcpServers": {
    "study-room": {
      "command": "uvx",
      "args": ["--from", "ucsd-study-room", "study-room-mcp"]
    }
  }
}
```

**Step 2: Commit**

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md MCP config to uvx"
```

---

### Task 6: Build and publish to PyPI

**Step 1: Clean old build artifacts**

```bash
cd /Users/theo/Documents/GitHub/ucsd-study-room
rm -rf dist/ build/ *.egg-info
```

**Step 2: Build**

```bash
python3 -m build
```

**Step 3: Upload to PyPI**

```bash
python3 -m twine upload dist/*
```

**Step 4: Verify uvx works with new version**

```bash
uv tool install --force ucsd-study-room
study-room status
```

Verify MCP entry point:
```bash
uvx --from ucsd-study-room study-room-mcp &
# Should start and wait for stdio input. Kill with Ctrl+C.
```

**Step 5: Commit version tag**

```bash
git tag v0.2.0
git push origin main --tags
```

---

### Task 7: E2E verification

**Step 1: Uninstall and reinstall from PyPI**

```bash
uv tool uninstall ucsd-study-room
uv tool install ucsd-study-room
```

**Step 2: Test CLI**

```bash
study-room status
study-room events
```

**Step 3: Test MCP server config**

Add to Claude Code MCP config:
```json
{
  "study-room": {
    "command": "uvx",
    "args": ["--from", "ucsd-study-room", "study-room-mcp"]
  }
}
```

Verify MCP tools work via Claude Code.
