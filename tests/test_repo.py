from app.models import Frame
from app.repo import BlameService


def test_blame_known(repo):
    p = repo.write("pkg/views.py", "def get_user():\n    return users['x']\n")
    repo.commit("add views", days_ago=1, author="Alice")

    info = BlameService().blame(Frame(file=str(p), line=2), str(p.parent))

    assert info.known is True
    assert info.author == "Alice"
    assert info.commit
    assert info.summary == "add views"
    assert info.churn >= 1


def test_dirty_file_detected(repo):
    p = repo.write("a.py", "x = 1\n")
    repo.commit("base")
    repo.write("a.py", "x = 2\n")  # change it but don't commit

    info = BlameService().blame(Frame(file=str(p), line=1), str(p.parent))

    assert info.known is True
    assert info.dirty is True


def test_uncommitted_line_falls_back_to_real_author(repo):
    p = repo.write("a.py", "x = 1\n")
    repo.commit("base", days_ago=1, author="Alice")
    repo.write("a.py", "x = 2\n")  # change line 1, don't commit

    info = BlameService().blame(Frame(file=str(p), line=1), str(p.parent))

    # git calls this "Not Committed Yet" with a zero hash - we swap in the real commit
    assert info.known is True
    assert info.uncommitted_line is True
    assert info.author == "Alice"
    assert info.short_commit != "0000000"


def test_untracked_file_unknown(repo):
    repo.write("tracked.py", "x = 1\n")
    repo.commit("base")
    p = repo.write("new.py", "y = 2\n")  # not added to git

    info = BlameService().blame(Frame(file=str(p), line=1), str(p.parent))

    assert info.known is False
    assert "untracked" in info.reason


def test_missing_file_unknown(repo):
    repo.write("a.py", "x = 1\n")
    repo.commit("base")
    missing = repo.path / "nope.py"

    info = BlameService().blame(Frame(file=str(missing), line=1), str(repo.path))

    assert info.known is False
    assert "not found" in info.reason


def test_pseudo_frame_unknown():
    info = BlameService().blame(Frame(file="<stdin>", line=1, pseudo=True), ".")

    assert info.known is False
    assert "dynamic" in info.reason


def test_not_a_repo(tmp_path):
    p = tmp_path / "lonely.py"
    p.write_text("x = 1\n", encoding="utf-8")

    info = BlameService().blame(Frame(file=str(p), line=1), str(tmp_path))

    assert info.known is False
