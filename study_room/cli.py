import asyncio
import typer
from rich.console import Console
from rich.table import Table

from study_room.config import load_config, save_config, CONFIG_PATH
from study_room.auth import login as auth_login, is_session_valid, SessionExpiredError
from study_room.booking import search_rooms, search_and_book, my_events, Room, Reservation, BookingError

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
    table.add_column("Room", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("ID", style="dim")
    for r in reservations:
        table.add_row(r.date, r.room, r.status, r.reservation_id)
    console.print(table)


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


if __name__ == "__main__":
    app()
