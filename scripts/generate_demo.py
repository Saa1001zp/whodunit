"""
draws docs/demo.svg with a sample of the output - for the README.
run: python scripts/generate_demo.py
"""
import io
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rich.console import Console  # noqa: E402

from app.models import BlameInfo, Frame, Suspect, TracebackInfo  # noqa: E402
from app.render import render  # noqa: E402

DAY = 86400.0


def build_demo(now: float) -> tuple[TracebackInfo, list[Suspect]]:
    info = TracebackInfo(exc_type="KeyError", exc_message="'user_id'")

    raw = [
        # file, line, func, depth, commit, author, days_ago, churn, dirty, summary, score
        ("app/views.py", 88, "get_user", 1.0, "a1b2c3d", "ivan", 2, 14, True, "hit rate fix", 4.21),
        ("app/serializers.py", 12, "to_repr", 0.5, "9f8e7d1", "olga", 95, 5, False, "add user dto", 1.44),
        ("app/lib/db.py", 45, "fetch_one", 0.0, "0001abc", "max", 430, 2, False, "init pool", 0.62),
    ]

    suspects = []
    for file, line, func, depth, commit, author, days, churn, dirty, summary, score in raw:
        frame = Frame(file=file, line=line, func=func, depth=depth)
        blame = BlameInfo(
            commit=commit + "0" * (40 - len(commit)),
            author=author,
            author_time=now - days * DAY,
            summary=summary,
            dirty=dirty,
            churn=churn,
            known=True,
        )
        suspect = Suspect(frame=frame, blame=blame, score=score)
        if dirty:
            suspect.reasons.append("uncommitted changes")
        if depth >= 0.99:
            suspect.reasons.append("exception point")
        if churn >= 10:
            suspect.reasons.append(f"hot file ({churn} commits)")
        suspects.append(suspect)

    return info, suspects


def main() -> None:
    now = time.time()
    info, suspects = build_demo(now)

    console = Console(record=True, file=io.StringIO(), width=104)
    console.print("[dim]$ whodunit crash.log[/]")
    render(info, suspects, console=console, now=now)

    out = ROOT / "docs" / "demo.svg"
    out.parent.mkdir(parents=True, exist_ok=True)
    console.save_svg(str(out), title="whodunit")
    print(f"saved {out}")


if __name__ == "__main__":
    main()
