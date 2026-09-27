"""
git wrapper - blame/status/log via subprocess, no gitpython.
if git is missing or the file is not in a repo we don't crash, we just say known=False
"""
import os
import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from app.models import BlameInfo, Frame


@lru_cache(maxsize=256)
def discover_root(directory: str) -> str | None:
    """
    find the git repository root for a directory. cached - a traceback has many frames.
    """
    try:
        proc = subprocess.run(
            ["git", "-C", directory, "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=10,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    root = proc.stdout.strip()
    return root or None


def _to_posix(path: str) -> str:
    return path.replace("\\", "/")


class Repo:
    """
    a single git repository. keeps its own blame cache so git is never called twice.
    """

    def __init__(self, root: str, churn_commits: int = 20, timeout: float = 10.0):
        self.root = root
        self.churn_commits = churn_commits
        self.timeout = timeout
        self._cache: dict[tuple[str, int], BlameInfo] = {}

    def _run(self, *args: str) -> tuple[int, str]:
        try:
            proc = subprocess.run(
                ["git", "-C", self.root, *args],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.timeout,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
            return 1, ""
        return proc.returncode, proc.stdout

    def _rel(self, abs_path: str) -> str:
        return _to_posix(os.path.relpath(abs_path, self.root))

    def _dirty(self, rel: str) -> bool:
        _, out = self._run("status", "--porcelain", "--", rel)
        return bool(out.strip())

    def _churn(self, rel: str) -> int:
        _, out = self._run("log", "--pretty=oneline", "-n", str(self.churn_commits), "--", rel)
        return sum(1 for line in out.splitlines() if line.strip())

    def _tracked(self, rel: str) -> bool:
        code, _ = self._run("ls-files", "--error-unmatch", "--", rel)
        return code == 0

    def _last_commit(self, rel: str) -> dict:
        # %x1f is a separator so names with spaces don't break parsing
        code, out = self._run("log", "-1", "--format=%H%x1f%an%x1f%at%x1f%s", "--", rel)
        if code != 0 or not out.strip():
            return {}
        parts = out.strip().split("\x1f")
        if len(parts) < 4:
            return {}
        try:
            when = float(parts[2] or 0)
        except ValueError:
            when = 0.0
        return {"commit": parts[0], "author": parts[1], "time": when, "summary": parts[3]}

    def blame_line(self, abs_path: str, line: int) -> BlameInfo:
        key = (abs_path, line)
        if key in self._cache:
            return self._cache[key]

        rel = self._rel(abs_path)
        if not os.path.exists(abs_path):
            info = BlameInfo(known=False, reason="file not found (path from another machine?)")
            self._cache[key] = info
            return info

        code, out = self._run("blame", "--porcelain", "-L", f"{line},{line}", "--", rel)
        if code != 0 or not out.strip():
            if not self._tracked(rel):
                info = BlameInfo(known=False, reason="file not in git (untracked)")
            else:
                info = BlameInfo(known=False, reason="git blame failed")
            self._cache[key] = info
            return info

        info = self._parse_porcelain(out)

        # a zero hash means the line is not committed yet, git calls this "Not Committed Yet".
        # we swap it for the file's last real commit and show the edit as a separate reason
        if info.commit and set(info.commit) == {"0"}:
            info.uncommitted_line = True
            info.dirty = True
            real = self._last_commit(rel)
            info.commit = real.get("commit", "")
            info.author = real.get("author", "")
            info.author_time = real.get("time", 0.0)
            info.summary = real.get("summary", "")
        else:
            info.dirty = self._dirty(rel)

        info.churn = self._churn(rel)
        self._cache[key] = info
        return info

    @staticmethod
    def _parse_porcelain(out: str) -> BlameInfo:
        info = BlameInfo(known=True)
        for line in out.splitlines():
            parts = line.split()
            # the first line is the commit hash (40 chars)
            if not info.commit and len(parts) >= 3 and len(parts[0]) == 40:
                info.commit = parts[0]
            elif line.startswith("author "):
                info.author = line[len("author ") :].strip()
            elif line.startswith("author-time "):
                try:
                    info.author_time = float(line[len("author-time ") :].strip())
                except ValueError:
                    info.author_time = 0.0
            elif line.startswith("summary "):
                info.summary = line[len("summary ") :].strip()
        return info


class BlameService:
    """
    facade for the cli: given a frame it returns BlameInfo and figures out the repo itself.
    """

    def __init__(self, churn_commits: int = 20, timeout: float = 10.0):
        self.churn_commits = churn_commits
        self.timeout = timeout
        self.has_git = shutil.which("git") is not None
        self._repos: dict[str, Repo | None] = {}

    def _repo_for(self, directory: str) -> Repo | None:
        if directory in self._repos:
            return self._repos[directory]
        root = discover_root(directory)
        repo = Repo(root, self.churn_commits, self.timeout) if root else None
        self._repos[directory] = repo
        return repo

    @staticmethod
    def resolve(file: str, cwd: str) -> Path | None:
        p = Path(file)
        if not p.is_absolute():
            p = Path(cwd) / p
        try:
            p = p.resolve()
        except OSError:
            return None
        return p if p.is_file() else None

    def blame(self, frame: Frame, cwd: str) -> BlameInfo:
        if not self.has_git:
            return BlameInfo(known=False, reason="git is not installed")
        if frame.not_a_file:
            return BlameInfo(known=False, reason="not a file (dynamic frame)")

        path = self.resolve(frame.file, cwd)
        if path is None:
            return BlameInfo(known=False, reason="file not found (path from another machine?)")

        repo = self._repo_for(str(path.parent))
        if repo is None:
            return BlameInfo(known=False, reason="not a git repository")

        return repo.blame_line(str(path), frame.line)
