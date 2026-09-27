"""
config - scoring weights and git settings, all through env so nothing is hardcoded
"""
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # how many frames to show at most
    max_frames: int = Field(default=30, alias="WHODUNIT_MAX_FRAMES")

    # scoring weights
    w_recency: float = Field(default=1.0, alias="WHODUNIT_W_RECENCY")
    w_dirty: float = Field(default=2.0, alias="WHODUNIT_W_DIRTY")
    w_churn: float = Field(default=0.5, alias="WHODUNIT_W_CHURN")
    w_depth: float = Field(default=0.7, alias="WHODUNIT_W_DEPTH")

    # after how many days freshness drops by half
    recency_decay_days: float = Field(default=30.0, alias="WHODUNIT_RECENCY_DECAY_DAYS")

    # churn window: how many recent commits of the file we look at
    churn_commits: int = Field(default=20, alias="WHODUNIT_CHURN_COMMITS")
    churn_ref: int = Field(default=10, alias="WHODUNIT_CHURN_REF")

    # git timeout
    git_timeout: float = Field(default=10.0, alias="WHODUNIT_GIT_TIMEOUT")


settings = Settings()
