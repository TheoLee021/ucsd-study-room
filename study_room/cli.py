import asyncio
import typer
from rich.console import Console
from rich.table import Table

from study_room.config import load_config, save_config, CONFIG_PATH
from study_room.auth import login as auth_login, is_session_valid, SessionExpiredError
from study_room.booking import search_rooms, search_and_book, my_events, cancel_reservation, Room, Reservation, CancelResult, CANCEL_REASONS, BookingError
from study_room.updater import get_current_version, check_pypi_latest, run_update, get_update_notice

app = typer.Typer(help="UCSD Study Room Booking Tool")
console = Console()


@app.command()
def login(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """SSO login + Duo Push authentication."""
    asyncio.run(auth_login(username, password))


@app.command()
def search(
    date: str = typer.Option(..., help="Date (YYYY-MM-DD)"),
    start: str = typer.Option(..., help="Start time (HH:MM)"),
    end: str = typer.Option(..., help="End time (HH:MM)"),
    book: bool = typer.Option(False, "--book", "-b", help="Book after search"),
):
    """Search available rooms. Use --book to book interactively."""
    if book:
        # search_and_book: search → select → book in a single browser
        async def pick_room(rooms: list[Room]) -> Room | None:
            table = Table(title="Available Rooms (Price Center)")
            table.add_column("#", style="cyan")
            table.add_column("Room", style="green")
            for i, room in enumerate(rooms, 1):
                table.add_row(str(i), room.name)
            console.print(table)

            choice = typer.prompt(f"Book a room? [1-{len(rooms)}/n]", default="n")
            if choice.lower() == "n":
                return None
            try:
                return rooms[int(choice) - 1]
            except (ValueError, IndexError):
                console.print("[red]Invalid selection.[/red]")
                return None

        try:
            result = asyncio.run(search_and_book(date, start, end, room_selector=pick_room))
            console.print(f"[green]{result}[/green]")
        except SessionExpiredError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        except BookingError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
    else:
        # search only
        try:
            rooms = asyncio.run(search_rooms(date, start, end))
        except SessionExpiredError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        except BookingError as e:
            console.print(f"[yellow]{e}[/yellow]")
            raise typer.Exit(1)

        if not rooms:
            console.print("[yellow]No rooms available for the selected time.[/yellow]")
            raise typer.Exit(0)

        table = Table(title="Available Rooms (Price Center)")
        table.add_column("#", style="cyan")
        table.add_column("Room", style="green")
        for i, room in enumerate(rooms, 1):
            table.add_row(str(i), room.name)
        console.print(table)


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
    table.add_column("Time", style="cyan")
    table.add_column("Room", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("ID", style="dim")
    for r in reservations:
        table.add_row(r.date, r.time, r.room, r.status, r.reservation_id)
    console.print(table)


@app.command()
def cancel(
    date: str = typer.Option(None, help="Date (YYYY-MM-DD)"),
    reason: str = typer.Option(None, help="Cancel reason"),
):
    """Cancel a reservation. Interactive selection if no date given."""
    # Step 1: If no date, show all events and let user pick
    if date is None:
        try:
            reservations = asyncio.run(my_events())
        except SessionExpiredError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        if not reservations:
            console.print("[yellow]No current reservations.[/yellow]")
            raise typer.Exit(0)

        table = Table(title="My Reservations")
        table.add_column("#", style="cyan")
        table.add_column("Date", style="green")
        table.add_column("Time", style="green")
        table.add_column("Room", style="green")
        table.add_column("Status", style="yellow")
        table.add_column("ID", style="dim")
        for i, r in enumerate(reservations, 1):
            table.add_row(str(i), r.date, r.time, r.room, r.status, r.reservation_id)
        console.print(table)

        choice = typer.prompt(f"Select reservation to cancel [1-{len(reservations)}/n]", default="n")
        if choice.lower() == "n":
            console.print("Cancelled.")
            raise typer.Exit(0)
        try:
            selected = reservations[int(choice) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            raise typer.Exit(1)

        date_for_cancel = selected.date  # raw date text from My Events table
        room_for_cancel = selected.room
    else:
        date_for_cancel = date
        room_for_cancel = None

    # Step 2: If no reason, show reason picker
    if reason is None:
        console.print("\n[bold]Cancel Reason:[/bold]")
        for i, r in enumerate(CANCEL_REASONS, 1):
            console.print(f"  {i}. {r}")
        reason_choice = typer.prompt(f"Select reason [1-{len(CANCEL_REASONS)}]")
        try:
            reason = CANCEL_REASONS[int(reason_choice) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            raise typer.Exit(1)

    # Step 3: Execute cancel
    try:
        result = asyncio.run(cancel_reservation(date_for_cancel, room_for_cancel, reason))
    except SessionExpiredError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except BookingError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if result.status == "cancelled":
        console.print(f"[green]{result.message}[/green]")
    elif result.status == "needs_selection":
        console.print(f"[yellow]{result.message}[/yellow]")
        table = Table(title="Matching Reservations")
        table.add_column("#", style="cyan")
        table.add_column("Date", style="green")
        table.add_column("Room", style="green")
        table.add_column("Status", style="yellow")
        for i, r in enumerate(result.reservations, 1):
            table.add_row(str(i), r.date, r.room, r.status)
        console.print(table)

        choice = typer.prompt(f"Select [1-{len(result.reservations)}/n]", default="n")
        if choice.lower() == "n":
            console.print("Cancelled.")
            raise typer.Exit(0)
        try:
            selected = result.reservations[int(choice) - 1]
        except (ValueError, IndexError):
            console.print("[red]Invalid selection.[/red]")
            raise typer.Exit(1)

        result2 = asyncio.run(cancel_reservation(date_for_cancel, selected.room, reason))
        if result2.status == "cancelled":
            console.print(f"[green]{result2.message}[/green]")
        else:
            console.print(f"[red]{result2.message}[/red]")
    elif result.status == "error":
        console.print(f"[red]{result.message}[/red]")


@app.command()
def config(
    name: str = typer.Option(None, help="Name"),
    email: str = typer.Option(None, help="Email"),
    attendees: int = typer.Option(None, help="Default number of attendees"),
):
    """View or update user settings."""
    cfg = load_config()
    changed = False

    if name is not None:
        cfg["name"] = name
        changed = True
    if email is not None:
        cfg["email"] = email
        changed = True
    if attendees is not None:
        cfg["default_attendees"] = attendees
        changed = True

    if changed:
        save_config(cfg)
        console.print("[green]Settings saved.[/green]")
    else:
        for key, value in cfg.items():
            console.print(f"  {key}: {value}")


@app.command()
def status():
    """Check current session status."""
    if is_session_valid():
        console.print("[green]Session valid[/green]")
    else:
        console.print("[yellow]Session expired — run 'study-room login'[/yellow]")


@app.command()
def update():
    """Update ucsd-study-room to the latest version."""
    current = get_current_version()
    latest = check_pypi_latest()

    if latest:
        console.print(f"Current version: {current}")
        console.print(f"Latest version:  {latest}")
    else:
        console.print(f"Current version: {current}")
        console.print("[yellow]Could not reach PyPI.[/yellow]")
        raise typer.Exit(1)

    status, message = run_update()
    if status == "updated":
        console.print(f"[green]✓ {message}[/green]")
    elif status == "current":
        console.print(f"[green]{message}[/green]")
    else:
        console.print(f"[red]✗ {message}[/red]")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
