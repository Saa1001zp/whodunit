"""
suspicion scoring - a pure function, which makes it easy to test.
score = w_recency * freshness + w_dirty * uncommitted + w_churn * churn + w_depth * depth
"""
from app.config import Settings
from app.models import BlameInfo, Frame, Suspect


def recency_score(age_days: float, decay_days: float) -> float:
    """
    a fresh change -> closer to 1. decay_days is the half-life.
    """
    if age_days == float("inf") or decay_days <= 0:
        return 0.0
    return 0.5 ** (age_days / decay_days)


def churn_score(churn: int, ref: int) -> float:
    """
    the more commits touched the file the hotter it is. at or above ref = 100%.
    """
    if ref <= 0:
        return 0.0
    return min(1.0, churn / ref)


def score_frame(frame: Frame, blame: BlameInfo, settings: Settings, now: float) -> Suspect:
    suspect = Suspect(frame=frame, blame=blame)

    # no git data - there is not much to suspect
    if not blame.known:
        suspect.reasons.append(blame.reason or "no data")
        return suspect

    age = suspect.age_days(now)
    recency = recency_score(age, settings.recency_decay_days)
    churn = churn_score(blame.churn, settings.churn_ref)

    suspect.score = (
        settings.w_recency * recency
        + settings.w_churn * churn
        + settings.w_depth * frame.depth
    )

    if blame.dirty or blame.uncommitted_line:
        suspect.score += settings.w_dirty
        if blame.uncommitted_line:
            suspect.reasons.append("edit in working tree")
        else:
            suspect.reasons.append("uncommitted changes")

    if frame.depth >= 0.99:
        suspect.reasons.append("exception point")
    if churn >= 0.9:
        suspect.reasons.append(f"hot file ({blame.churn} commits)")
    if age <= 3:
        suspect.reasons.append(f"changed {age:.0f}d ago")

    return suspect


def score_all(
    pairs: list[tuple[Frame, BlameInfo]], settings: Settings, now: float
) -> list[Suspect]:
    suspects = [score_frame(frame, blame, settings, now) for frame, blame in pairs]
    suspects.sort(key=lambda s: s.score, reverse=True)
    return suspects
