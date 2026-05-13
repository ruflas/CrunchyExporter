from dataclasses import dataclass, field
from typing import Optional


@dataclass
class CRToken:
    access_token: str
    refresh_token: str
    account_id: str


@dataclass
class Episode:
    series_id: str
    series_title: str
    season_number: int
    episode_number: float
    episode_title: str
    episode_id: str
    watched_at: Optional[str] = None
    fully_watched: bool = False

    def to_dict(self) -> dict:
        return {
            "series_id": self.series_id,
            "series_title": self.series_title,
            "season_number": self.season_number,
            "episode_number": self.episode_number,
            "episode_title": self.episode_title,
            "episode_id": self.episode_id,
            "watched_at": self.watched_at,
            "fully_watched": self.fully_watched,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Episode":
        return cls(**data)


@dataclass
class SeriesSummary:
    series_id: str
    series_title: str
    episodes_watched: list[int] = field(default_factory=list)
    max_episode: int = 0
    first_watched_at: Optional[str] = None  # ISO-8601 date of earliest episode
    last_watched_at: Optional[str] = None   # ISO-8601 date of most recent episode

    @property
    def total_watched(self) -> int:
        return len(self.episodes_watched)
