# ucsd-study-room

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

A CLI tool and MCP server that automatically searches and books UCSD Price Center study rooms (Rooms 1--8) through the EMS Cloud booking system.

## Features

- **Headless browser automation** -- Searches and books rooms using Playwright with real Chrome, no browser window required
- **UCSD SSO + Duo Push authentication** -- Handles SAML-based single sign-on and Duo two-factor authentication
- **Session persistence** -- Saves browser sessions (cookies + localStorage) for reuse; credentials stored securely in the system keyring (macOS Keychain, Windows Credential Locker, or Linux SecretService)
- **Automatic re-authentication** -- When SSO expires, opens a headed browser for Duo Push re-verification without requiring you to re-enter credentials
- **CLI interface** -- Simple `study-room` command for searching and booking from the terminal
- **MCP server** -- Integrates with Claude Code so you can book rooms using natural language

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

## Getting Started with Claude Code

If you have [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed, copy and paste this prompt to set up everything automatically:

```
Install the ucsd-study-room MCP server:
1. Run: pip install ucsd-study-room && playwright install chromium
2. Add to .claude/settings.json mcpServers: {"study-room": {"command": "python", "args": ["-m", "study_room.mcp_server"]}}
3. Run: study-room config --name "MY NAME" --email "MY_EMAIL@ucsd.edu"
4. Run: study-room login
```

Replace `MY NAME` and `MY_EMAIL@ucsd.edu` with your actual name and UCSD email before pasting.

Once set up, you can use natural language in Claude Code:

- "Search for available study rooms tomorrow from 2pm to 4pm"
- "Book Price Center Study Room 3 on March 11 from 3pm to 5pm"
- "Are there any rooms open this Friday afternoon?"

## Manual Installation

```bash
pip install ucsd-study-room
playwright install chromium
```

## CLI Quick Start

**1. Set your contact info (required before booking):**

```bash
study-room config --name "Your Name" --email "you@ucsd.edu"
```

**2. Log in with your UCSD credentials (first time only):**

```bash
study-room login
```

A Chrome window will open. Enter your UCSD SSO credentials when prompted, then approve the Duo Push notification on your phone. Your session and credentials are saved for future use.

**3. Search for available rooms:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00
```

**4. Search and book interactively:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00 --book
```

## CLI Commands

| Command | Description |
|---------|-------------|
| `study-room login` | SSO login with Duo Push (opens browser for first-time auth) |
| `study-room search` | Search available rooms with `--date`, `--start`, `--end` options |
| `study-room search --book` | Search and book a room interactively |
| `study-room config` | View or set user info (`--name`, `--email`, `--attendees`) |
| `study-room status` | Check whether the current session is valid |

## MCP Server Setup (Manual)

Add the following to your `.claude/settings.json`:

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

### Available MCP Tools

| Tool | Description |
|------|-------------|
| `search_rooms` | Search for available rooms by date and time range |
| `book_room` | Book a specific room (use after `search_rooms`) |
| `login` | Authenticate via UCSD SSO + Duo Push |

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
