"""
whodunit dataclasses - a stack frame, git blame info and the final suspect
"""
from dataclasses import dataclass, field


@dataclass
class Frame:
    file: str = ""
    line: int = 0
    func: str = ""
    source: str = ""
    pseudo: bool = False  # <stdin>, <string>, <frozen importlib...>
    depth: float = 0.0  # 0..1, where 1 = the exception point (last frame)

    @property
    def location(self) -> str:
        return f"{self.file}:{self.line}"

    @property
    def not_a_file(self) -> bool:
        # compiled/dynamic frames - there is nothing to blame here
        return self.pseudo or not self.file or self.file.startswith("<")


@dataclass
class BlameInfo:
    commit: str = ""
    author: str = ""
    author_time: float = 0.0
    summary: str = ""
    dirty: bool = False  # the file has uncommitted edits
    uncommitted_line: bool = False  # this exact line is not committed yet
    churn: int = 0  # how many commits touched the file in the churn window
    known: bool = True  # did we manage to get any git info at all
    reason: str = ""  # why unknown (no git, not a repo, untracked...)

    @property
    def short_commit(self) -> str:
        return self.commit[:7] if self.commit else "-"


@dataclass
class Suspect:
    frame: Frame
    blame: BlameInfo
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)

    def age_days(self, now: float) -> float:
        if not self.blame.author_time:
            return float("inf")
        return max(0.0, (now - self.blame.author_time) / 86400)


@dataclass
class TracebackInfo:
    frames: list[Frame] = field(default_factory=list)
    exc_type: str = ""
    exc_message: str = ""

    @property
    def exception(self) -> str:
        if self.exc_message:
            return f"{self.exc_type}: {self.exc_message}"
        return self.exc_type
