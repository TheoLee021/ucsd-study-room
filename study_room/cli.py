import asyncio
import typer
from rich.console import Console
from rich.table import Table

from study_room.config import load_config, save_config, CONFIG_PATH
from study_room.auth import login as auth_login, is_session_valid, SessionExpiredError
from study_room.booking import search_rooms, search_and_book, Room, BookingError

app = typer.Typer(help="UCSD Study Room Booking Tool")
console = Console()


@app.command()
def login(
    username: str = typer.Option(..., prompt=True),
    password: str = typer.Option(..., prompt=True, hide_input=True),
):
    """SSO 로그인 + Duo Push 인증."""
    asyncio.run(auth_login(username, password))


@app.command()
def search(
    date: str = typer.Option(..., help="날짜 (YYYY-MM-DD)"),
    start: str = typer.Option(..., help="시작 시간 (HH:MM)"),
    end: str = typer.Option(..., help="종료 시간 (HH:MM)"),
    book: bool = typer.Option(False, "--book", "-b", help="검색 후 바로 예약"),
):
    """빈 방을 검색하고, --book 옵션 시 예약까지 진행."""
    if book:
        # search_and_book: 하나의 브라우저에서 검색 → 선택 → 예약
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
                console.print("[red]잘못된 선택입니다.[/red]")
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
            console.print("[yellow]해당 시간에 빈 방이 없습니다.[/yellow]")
            raise typer.Exit(0)

        table = Table(title="Available Rooms (Price Center)")
        table.add_column("#", style="cyan")
        table.add_column("Room", style="green")
        for i, room in enumerate(rooms, 1):
            table.add_row(str(i), room.name)
        console.print(table)


@app.command()
def config(
    name: str = typer.Option(None, help="이름"),
    email: str = typer.Option(None, help="이메일"),
    attendees: int = typer.Option(None, help="기본 참석자 수"),
):
    """사용자 설정을 변경한다."""
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
        console.print("[green]설정이 저장되었습니다.[/green]")
    else:
        for key, value in cfg.items():
            console.print(f"  {key}: {value}")


@app.command()
def status():
    """현재 세션 상태를 확인한다."""
    if is_session_valid():
        console.print("[green]세션 유효[/green]")
    else:
        console.print("[yellow]세션 만료 — 'study-room login' 필요[/yellow]")


if __name__ == "__main__":
    app()
