# ucsd-study-room

[한국어](README.ko.md)

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](https://opensource.org/licenses/MIT)

Automate UCSD Price Center study room booking with your AI assistant or from the terminal.

**What you can do:**

- **Search** available rooms by date and time
- **Book** a room instantly
- **Cancel** reservations with a reason
- **View** your current reservations

Works with Claude Code, Codex CLI, Gemini CLI, Cursor, and any MCP-compatible client.

## Quick Start

If you're using an MCP-compatible AI assistant (Claude Code, Codex CLI, etc.), simply copy and paste this prompt:

```
Install the ucsd-study-room MCP server:
1. Run: uv tool install ucsd-study-room && uvx --from ucsd-study-room playwright install chromium
2. Add "study-room" to your MCP config: {"command": "uvx", "args": ["--from", "ucsd-study-room", "study-room-mcp"]}
3. Run: study-room config --name "MY NAME" --email "MY_EMAIL@ucsd.edu"
4. Run: study-room login
```

Replace `MY NAME` and `MY_EMAIL@ucsd.edu` with your actual name and UCSD email before pasting. Your AI assistant will handle the rest.

Once set up, just ask your AI assistant in natural language:

- "Search for available study rooms tomorrow from 2pm to 4pm"
- "Book Price Center Study Room on March 11 from 3pm to 5pm"
- "Cancel my reservation on March 13"
- "Show my current reservations"

## Requirements

- Python 3.11 or later
- Google Chrome installed
- UCSD account with Duo Push enabled

### Platform Support

| Platform | Status          | Notes                                                                                                                                                                           |
| -------- | --------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| macOS    | Fully supported | Credentials stored in Keychain                                                                                                                                                  |
| Windows  | Supported       | Credentials stored in Windows Credential Locker                                                                                                                                 |
| Linux    | Supported       | Requires `gnome-keyring` or `kwallet` for credential storage; falls back to manual login if unavailable. Run `playwright install --with-deps chromium` for system dependencies. |

## Manual Installation

```bash
uv tool install ucsd-study-room
uvx --from ucsd-study-room playwright install chromium
```

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
    "command": "uvx",
    "args": ["--from", "ucsd-study-room", "study-room-mcp"]
  }
}
```

### Compatible Clients

| Client                                  | Type        | Config Location         |
| --------------------------------------- | ----------- | ----------------------- |
| Claude Code / Codex CLI / Gemini CLI    | CLI         | Each CLI's config file  |
| Claude Desktop / Codex Desktop          | Desktop App | Each app's settings     |
| Cursor / Windsurf / Antigravity / Cline | IDE         | Each IDE's MCP settings |

Once configured, you can use natural language to manage bookings:

- "Search for available study rooms tomorrow from 2pm to 4pm"
- "Book Price Center Study Room 3 on March 11 from 3pm to 5pm"
- "Cancel my reservation on March 13"
- "Are there any rooms open this Friday afternoon?"

### Available MCP Tools

| Tool                   | Description                                               |
| ---------------------- | --------------------------------------------------------- |
| `search_rooms`         | Search for available rooms by date and time range         |
| `book_room`            | Book a specific room (use after `search_rooms`)           |
| `cancel_reservation`   | Cancel a reservation by date with a cancel reason         |
| `my_events`            | List current reservations with date, room, status, and ID |
| `login`                | Authenticate via UCSD SSO + Duo Push                      |

## CLI Usage

### Commands

| Command                    | Description                                                      |
| -------------------------- | ---------------------------------------------------------------- |
| `study-room login`         | SSO login with Duo Push (opens browser for first-time auth)      |
| `study-room search`        | Search available rooms with `--date`, `--start`, `--end` options |
| `study-room search --book` | Search and book a room interactively                             |
| `study-room cancel`        | Cancel a reservation interactively or with `--date`, `--reason`  |
| `study-room events`        | Show current reservations                                        |
| `study-room config`        | View or set user info (`--name`, `--email`, `--attendees`)       |
| `study-room status`        | Check whether the current session is valid                       |

### Examples

**Search for available rooms:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00
```

**Search and book interactively:**

```bash
study-room search --date 2026-03-11 --start 15:00 --end 17:00 --book
```

**Cancel a reservation:**

```bash
study-room cancel                              # interactive selection
study-room cancel --date 2026-03-13            # by date (prompts for reason)
study-room cancel --date 2026-03-13 --reason "Changed Date"
```

## How It Works

1. **Browser automation** -- Uses Playwright with real Chrome (`channel="chrome"`) in headless mode to interact with the EMS Cloud booking system.
2. **Authentication** -- Navigates to the UCSD SAML SSO page, submits credentials, and waits for Duo Push approval. On first login, a headed browser window opens for the Duo flow.
3. **Session management** -- After authentication, cookies and browser storage state are saved to `~/.study-room/`. Credentials are stored in the system keyring via the `keyring` library (macOS Keychain, Windows Credential Locker, or Linux SecretService). Sessions are valid for 7 days.
4. **Auto re-login** -- When a session expires during a search or booking operation, the tool automatically opens a headed browser, loads credentials from the system keyring, and re-authenticates with Duo Push.
5. **Room search** -- Navigates to the EMS booking page, fills in date and time fields, and parses available rooms by inspecting the DOM for booking buttons.
6. **Booking** -- Clicks the add-to-cart button for the selected room, fills in the reservation form (name, email, terms), and submits the reservation.
7. **Cancellation** -- Navigates to My Events, clicks the reservation link, selects a cancel reason from the dropdown, and confirms the cancellation.

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
