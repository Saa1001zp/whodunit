"""
output - the exception panel plus a suspect table. there is --json for scripts
"""
import json
import sys

from rich import box
from rich.console import Console, RenderableType
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from app.models import Suspect, TracebackInfo

BAR_WIDTH = 8


class _Symbols:
    """
    on win consoles with cp1251 the block chars and unicode dash don't fit,
    so we keep an ascii fallback.
    """

    def __init__(self, ascii_mode: bool) -> None:
        self.ascii = ascii_mode
        self.bar_full = "#" if ascii_mode else "█"
        self.bar_empty = "-" if ascii_mode else "░"
        self.ellipsis = "..." if ascii_mode else "…"
        self.dash = "-" if ascii_mode else "—"
        self.box = box.ASCII if ascii_mode else box.ROUNDED


SYM = _Symbols(False)


def set_ascii(value: bool) -> None:
    global SYM
    SYM = _Symbols(value)


def enable_utf8() -> bool:
    """
    try to switch stdout/stderr to utf-8. if it fails we fall back to ascii.
    called early (at the entry point), otherwise --help breaks on a cp1251 console.
    """
    ok = True
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", "") or "").lower()
        if "utf" in enc or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            ok = False
    return ok


def make_console(no_color: bool = False) -> Console:
    set_ascii(not enable_utf8())
    if no_color:
        return Console(color_system=None, highlight=False)
    return Console(highlight=False)


def short_path(path: str, max_len: int = 42) -> str:
    p = path.replace("\\", "/")
    if len(p) <= max_len:
        return p
    keep = max_len - len(SYM.ellipsis)
    return SYM.ellipsis + p[-keep:]


def age_str(age_days: float) -> str:
    if age_days == float("inf"):
        return "?"
    if age_days < 1:
        return f"{age_days * 24:.0f}h"
    if age_days < 60:
        return f"{age_days:.0f}d"
    if age_days < 365:
        return f"{age_days / 30:.0f}mo"
    return f"{age_days / 365:.0f}y"


def bar(value: float, maximum: float, width: int = BAR_WIDTH) -> str:
    if maximum <= 0:
        filled = 0
    else:
        filled = round(width * min(1.0, value / maximum))
    return SYM.bar_full * filled + SYM.bar_empty * (width - filled)


def _suspect_row(rank: int, suspect: Suspect, maximum: float, now: float) -> list[RenderableType]:
    frame = suspect.frame
    blame = suspect.blame

    if blame.known:
        commit = blame.short_commit
        age = age_str(suspect.age_days(now))
        loc_style = "bold red" if rank == 1 else "default"
        bar_text = Text(bar(suspect.score, maximum), style="red" if rank == 1 else "yellow")
    else:
        commit = SYM.dash
        age = "?"
        loc_style = "dim"
        bar_text = Text(bar(0, maximum), style="dim")

    location = Text(f"{short_path(frame.file)}:{frame.line}", style=loc_style)
    why = ", ".join(suspect.reasons)

    return [
        Text(str(rank), style="dim"),
        location,
        Text(frame.func or "?", style="cyan"),
        Text(commit, style="magenta"),
        Text(age, justify="right"),
        bar_text,
        Text(why, style="dim"),
    ]


def render(
    info: TracebackInfo,
    suspects: list[Suspect],
    console: Console | None = None,
    top: int | None = None,
    now: float = 0.0,
) -> None:
    console = console or make_console()

    exc = info.exception or "traceback without an explicit exception"
    console.print(Panel(exc, title="[bold]exception[/]", border_style="red", box=SYM.box, expand=False))

    shown = suspects[:top] if top else suspects
    if not shown:
        console.print("[yellow]found no frames in this traceback[/]")
        return

    maximum = max((s.score for s in shown), default=0.0)
    table = Table(box=SYM.box, header_style="bold", expand=False)
    table.add_column("#", justify="right", width=3, style="dim")
    table.add_column("location", overflow="fold", min_width=18)
    table.add_column("function", style="cyan", no_wrap=True)
    table.add_column("commit", style="magenta", no_wrap=True)
    table.add_column("age", justify="right", no_wrap=True)
    table.add_column("suspicion", no_wrap=True)
    table.add_column("why", style="dim", no_wrap=True, overflow="ellipsis", max_width=28)

    for rank, suspect in enumerate(shown, start=1):
        table.add_row(*_suspect_row(rank, suspect, maximum, now))

    console.print(table)

    best = shown[0]
    if best.blame.known:
        console.print(
            f"[bold red]Top suspect:[/] [bold]{short_path(best.frame.file)}:{best.frame.line}[/]"
            f" {SYM.dash} changed by [green]{best.blame.author}[/]"
            + (f" ([italic]{best.blame.summary}[/])" if best.blame.summary else "")
        )
    else:
        console.print("[yellow]no git data, so there is no culprit to name[/]")


def to_json(info: TracebackInfo, suspects: list[Suspect], top: int | None, now: float) -> str:
    shown = suspects[:top] if top else suspects
    payload = {
        "exception": {
            "type": info.exc_type,
            "message": info.exc_message,
        },
        "frames_count": len(info.frames),
        "suspects": [
            {
                "location": f"{s.frame.file}:{s.frame.line}",
                "function": s.frame.func,
                "score": round(s.score, 3),
                "commit": s.blame.short_commit if s.blame.known else None,
                "author": s.blame.author if s.blame.known else None,
                "age_days": (None if not s.blame.known else round(s.age_days(now), 2)),
                "dirty": s.blame.dirty,
                "churn": s.blame.churn,
                "reasons": s.reasons,
            }
            for s in shown
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)
