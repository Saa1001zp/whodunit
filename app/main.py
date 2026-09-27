"""
typer cli - takes a traceback from wherever you want and shows the culprit via git blame
"""
import sys
import time
from pathlib import Path

import typer

from app import __version__
from app.config import settings
from app.parser import parse_traceback
from app.render import make_console, render, to_json
from app.repo import BlameService
from app.score import score_all

app = typer.Typer(
    add_completion=False,
    help="whodunit - find the culprit in a traceback using git blame",
)


def _read_input(path: str | None, clipboard: bool) -> str:
    if clipboard:
        import pyperclip

        try:
            return pyperclip.paste()
        except Exception as exc:  # the clipboard may be unavailable (server, ssh)
            raise typer.BadParameter(f"could not read the clipboard: {exc}") from exc

    if path:
        p = Path(path)
        if not p.is_file():
            raise typer.BadParameter(f"file not found: {path}")
        return p.read_text(encoding="utf-8", errors="replace")

    if not sys.stdin.isatty():
        return sys.stdin.read()

    raise typer.BadParameter("pass a file, use --clipboard, or pipe a traceback into stdin")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"whodunit {__version__}")
        raise typer.Exit()


@app.command()
def main(
    path: str | None = typer.Argument(None, help="file with the traceback (or stdin)"),
    clipboard: bool = typer.Option(False, "--clipboard", help="read the traceback from the clipboard"),
    as_json: bool = typer.Option(False, "--json", help="print the result as json"),
    top: int | None = typer.Option(None, "--top", "-n", help="show only the top N suspects"),
    no_color: bool = typer.Option(False, "--no-color", help="disable colors"),
    version: bool = typer.Option(
        False, "--version", callback=_version_callback, is_eager=True, help="show version"
    ),
) -> None:
    """
    parses the traceback and ranks frames by suspicion.
    """
    try:
        text = _read_input(path, clipboard)
    except typer.BadParameter as exc:
        typer.secho(str(exc), fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc

    info = parse_traceback(text)
    console = make_console(no_color=no_color)

    if not info.frames:
        console.print("[yellow]found no frames - is this really a python traceback?[/]")
        raise typer.Exit(code=1)

    now = time.time()
    cwd = str(Path.cwd())
    blame = BlameService(churn_commits=settings.churn_commits, timeout=settings.git_timeout)
    pairs = [(frame, blame.blame(frame, cwd)) for frame in info.frames]

    # we don't print a wall of frames - keep the last ones (closer to the exception)
    if settings.max_frames:
        pairs = pairs[-settings.max_frames :]

    suspects = score_all(pairs, settings, now)

    if as_json:
        # via typer.echo so rich doesn't eat square brackets as markup
        typer.echo(to_json(info, suspects, top, now))
    else:
        render(info, suspects, console=console, top=top, now=now)


if __name__ == "__main__":
    app()
