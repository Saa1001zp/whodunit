"""
shared fixtures - a throwaway git repository with pinned commit dates
"""
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

import pytest


def _iso_days_ago(days: float) -> str:
    return (datetime.now() - timedelta(days=days)).isoformat(timespec="seconds")


def _git(*args: str, cwd: Path, env: dict | None = None) -> None:
    full_env = os.environ.copy()
    if env:
        full_env.update(env)
    subprocess.run(
        ["git", *args],
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env=full_env,
    )


class RepoBuilder:
    """
    a small helper to lay out a repo with history and dates.
    """

    def __init__(self, path: Path):
        self.path = Path(path)

    def init(self) -> "RepoBuilder":
        self.path.mkdir(parents=True, exist_ok=True)
        _git("init", "-q", cwd=self.path)
        _git("config", "user.email", "dev@example.com", cwd=self.path)
        _git("config", "user.name", "Dev", cwd=self.path)
        _git("config", "commit.gpgsign", "false", cwd=self.path)
        # so the auto branch detection doesn't make noise
        _git("symbolic-ref", "HEAD", "refs/heads/main", cwd=self.path)
        return self

    def write(self, rel: str, text: str) -> Path:
        p = self.path / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return p

    def commit(self, msg: str, days_ago: float = 0.0, author: str = "Dev") -> None:
        when = _iso_days_ago(days_ago)
        env = {
            "GIT_AUTHOR_DATE": when,
            "GIT_COMMITTER_DATE": when,
            "GIT_AUTHOR_NAME": author,
            "GIT_AUTHOR_EMAIL": f"{author.lower()}@example.com",
            "GIT_COMMITTER_NAME": author,
            "GIT_COMMITTER_EMAIL": f"{author.lower()}@example.com",
        }
        _git("add", "-A", cwd=self.path)
        _git("commit", "-q", "-m", msg, cwd=self.path, env=env)


@pytest.fixture
def repo(tmp_path) -> RepoBuilder:
    return RepoBuilder(tmp_path / "repo").init()
