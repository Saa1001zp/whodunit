from app.config import Settings
from app.models import BlameInfo, Frame
from app.score import churn_score, recency_score, score_all, score_frame


def make_settings(**overrides) -> Settings:
    base = dict(
        max_frames=30,
        w_recency=1.0,
        w_dirty=2.0,
        w_churn=0.5,
        w_depth=0.7,
        recency_decay_days=30.0,
        churn_commits=20,
        churn_ref=10,
        git_timeout=10.0,
    )
    base.update(overrides)
    return Settings(**base)


NOW = 1_800_000_000.0
DAY = 86400.0


def test_recency_half_life():
    assert recency_score(0.0, 30.0) == 1.0
    assert recency_score(30.0, 30.0) == 0.5
    assert recency_score(float("inf"), 30.0) == 0.0
    assert recency_score(10.0, 0.0) == 0.0


def test_churn_caps_at_one():
    assert churn_score(0, 10) == 0.0
    assert churn_score(5, 10) == 0.5
    assert churn_score(10, 10) == 1.0
    assert churn_score(999, 10) == 1.0
    assert churn_score(5, 0) == 0.0


def test_dirty_adds_weight_and_reason():
    frame = Frame(file="a.py", line=1, depth=0.0)
    blame = BlameInfo(known=True, author_time=NOW, churn=0, dirty=True)
    suspect = score_frame(frame, blame, make_settings(), NOW)
    assert suspect.score >= 2.0  # w_dirty
    assert "uncommitted changes" in suspect.reasons


def test_recent_change_beats_old():
    settings = make_settings()
    fresh = Frame(file="fresh.py", line=1, depth=0.0)
    old = Frame(file="old.py", line=1, depth=0.0)
    fresh_blame = BlameInfo(known=True, author_time=NOW - 1 * DAY, churn=0)
    old_blame = BlameInfo(known=True, author_time=NOW - 900 * DAY, churn=0)
    assert score_frame(fresh, fresh_blame, settings, NOW).score > score_frame(
        old, old_blame, settings, NOW
    ).score


def test_exception_point_gets_bonus():
    settings = make_settings()
    blame = BlameInfo(known=True, author_time=NOW - 400 * DAY, churn=0)
    top = Frame(file="a.py", line=1, depth=1.0)
    bottom = Frame(file="a.py", line=2, depth=0.0)
    top_suspect = score_frame(top, blame, settings, NOW)
    assert "exception point" in top_suspect.reasons
    assert top_suspect.score > score_frame(bottom, blame, settings, NOW).score


def test_unknown_blame_scores_zero():
    frame = Frame(file="<stdin>", line=1, pseudo=True)
    suspect = score_frame(frame, BlameInfo(known=False, reason="no data"), make_settings(), NOW)
    assert suspect.score == 0.0
    assert suspect.reasons == ["no data"]


def test_score_all_sorted_desc():
    settings = make_settings()
    hot = (Frame(file="hot.py", line=1, depth=1.0), BlameInfo(known=True, author_time=NOW))
    cold = (Frame(file="cold.py", line=1, depth=0.0), BlameInfo(known=True, author_time=NOW - 900 * DAY))
    suspects = score_all([cold, hot], settings, NOW)
    assert suspects[0].frame.file == "hot.py"
