# My Events Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add reservation lookup by parsing the EMS MY EVENTS page (CURRENT tab).

**Architecture:** Add `Reservation` dataclass and `my_events()` async function to booking.py that navigates to BrowseReservations.aspx and parses the table DOM. Expose via CLI (`study-room events`) and MCP (`my_events` tool).

**Tech Stack:** Python, Playwright, Typer, MCP

---

### Task 1: Add Reservation dataclass and my_events() to booking.py

**Files:**
- Modify: `study_room/booking.py`

**Step 1: Add Reservation dataclass after Room dataclass (line ~16)**

```python
@dataclass
class Reservation:
    date: str
    room: str
    status: str
    reservation_id: str
```

**Step 2: Add my_events() public function**

```python
MY_EVENTS_URL = "https://ucsdevents.emscloudservice.com/web/BrowseReservations.aspx"


async def _open_and_get_events(playwright) -> list[Reservation]:
    context = await get_authenticated_context(playwright, headless=True)
    if context is None:
        raise SessionExpiredError("Session expired. Please run 'study-room login' first.")

    page = await context.new_page()
    try:
        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")

        result = await authenticate(page)
        if result == "relogin_needed":
            return await _open_and_get_events(playwright)

        await page.goto(MY_EVENTS_URL)
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(2)

        rows = page.locator("table.table tbody tr")
        count = await rows.count()

        reservations = []
        for i in range(count):
            row = rows.nth(i)
            cols = row.locator("td")
            if await cols.count() < 7:
                continue

            date_text = (await cols.nth(1).inner_text()).strip().split("/")[0].strip()
            location_text = (await cols.nth(2).inner_text()).strip()
            room = location_text.split(" - ")[-1].strip() if " - " in location_text else location_text
            reservation_id = (await cols.nth(5).inner_text()).strip()
            status = (await cols.nth(6).inner_text()).strip()

            reservations.append(Reservation(
                date=date_text,
                room=room,
                status=status,
                reservation_id=reservation_id,
            ))

        return reservations
    finally:
        if page and page.context.browser.is_connected():
            await page.context.browser.close()


async def my_events() -> list[Reservation]:
    async with async_playwright() as p:
        return await _open_and_get_events(p)
```

**Step 3: Commit**

```bash
git add study_room/booking.py
git commit -m "feat: add my_events() for reservation lookup"
```

---

### Task 2: Add `study-room events` CLI command

**Files:**
- Modify: `study_room/cli.py`

**Step 1: Add import for Reservation and my_events**

Add `Reservation` and `my_events` to the booking import line.

**Step 2: Add events command**

```python
@app.command()
def events():
    """Show current reservations."""
    try:
        reservations = asyncio.run(my_events())
    except SessionExpiredError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if not reservations:
        console.print("[yellow]No current reservations.[/yellow]")
        raise typer.Exit(0)

    table = Table(title="My Reservations")
    table.add_column("Date", style="cyan")
    table.add_column("Room", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("ID", style="dim")
    for r in reservations:
        table.add_row(r.date, r.room, r.status, r.reservation_id)
    console.print(table)
```

**Step 3: Commit**

```bash
git add study_room/cli.py
git commit -m "feat: add 'study-room events' CLI command"
```

---

### Task 3: Add my_events MCP tool

**Files:**
- Modify: `study_room/mcp_server.py`

**Step 1: Add import for my_events and Reservation**

**Step 2: Add Tool to list_tools()**

```python
Tool(
    name="my_events",
    description="List current reservations. Returns upcoming bookings with date, room, status, and ID.",
    inputSchema={
        "type": "object",
        "properties": {},
        "required": [],
    },
),
```

**Step 3: Add handler in call_tool()**

```python
elif name == "my_events":
    reservations = await my_events()
    if not reservations:
        return [TextContent(type="text", text="No current reservations.")]
    lines = [f"{len(reservations)} reservation(s):"]
    for r in reservations:
        lines.append(f"  - {r.date} | {r.room} | {r.status} (ID: {r.reservation_id})")
    return [TextContent(type="text", text="\n".join(lines))]
```

**Step 4: Commit**

```bash
git add study_room/mcp_server.py
git commit -m "feat: add my_events MCP tool"
```

---

### Task 4: Update READMEs

**Files:**
- Modify: `README.md`
- Modify: `README.ko.md`

**Step 1: Add to CLI commands table and MCP tools table in both files**

**Step 2: Commit**

```bash
git add README.md README.ko.md
git commit -m "docs: add events command and my_events tool to READMEs"
```
