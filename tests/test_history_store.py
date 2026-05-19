import pytest
from src.storage.history_store import HistoryStore
from src.crunchyroll.models import Episode


def _ep(sid="s1", title="Naruto", ep_num=1, ep_id=None, watched=None, fully=False):
    return Episode(
        series_id=sid,
        series_title=title,
        season_number=1,
        episode_number=ep_num,
        episode_title=f"Episode {ep_num}",
        episode_id=ep_id or f"{sid}-{ep_num}",
        watched_at=watched,
        fully_watched=fully,
    )


@pytest.fixture
def store(tmp_path):
    return HistoryStore(tmp_path / "history.json")


class TestSeriesSummaries:
    def test_groups_by_series_id(self, store):
        store.update([_ep("s1", "Naruto", 1), _ep("s1", "Naruto", 2), _ep("s2", "Bleach", 1)])
        summaries = {s.series_id: s for s in store.series_summaries()}
        assert set(summaries) == {"s1", "s2"}

    def test_max_episode_is_highest(self, store):
        store.update([_ep("s1", ep_num=3), _ep("s1", ep_num=7), _ep("s1", ep_num=1)])
        s = store.series_summaries()[0]
        assert s.max_episode == 7

    def test_movie_episode_zero_treated_as_one(self, store):
        store.update([_ep("m1", "Movie", ep_num=0, ep_id="m1-0")])
        s = store.series_summaries()[0]
        assert s.max_episode == 1

    def test_first_watched_at_is_earliest(self, store):
        store.update([
            _ep("s1", ep_num=1, watched="2024-01-02T00:00:00+00:00"),
            _ep("s1", ep_num=2, watched="2024-01-01T00:00:00+00:00"),
        ])
        s = store.series_summaries()[0]
        assert s.first_watched_at == "2024-01-01T00:00:00+00:00"

    def test_last_watched_at_is_latest(self, store):
        store.update([
            _ep("s1", ep_num=1, watched="2024-01-01T00:00:00+00:00"),
            _ep("s1", ep_num=2, watched="2024-03-15T00:00:00+00:00"),
        ])
        s = store.series_summaries()[0]
        assert s.last_watched_at == "2024-03-15T00:00:00+00:00"


class TestUpdate:
    def test_no_duplicates(self, store):
        ep = _ep("s1", ep_num=1, ep_id="e1")
        store.update([ep])
        store.update([ep])
        assert len(store) == 1

    def test_returns_new_count(self, store):
        ep1 = _ep("s1", ep_num=1, ep_id="e1")
        ep2 = _ep("s1", ep_num=2, ep_id="e2")
        assert store.update([ep1]) == 1
        assert store.update([ep1, ep2]) == 1

    def test_incremental_preserves_old_episodes(self, store):
        store.update([_ep("s1", ep_num=1, ep_id="e1")])
        store.update([_ep("s1", ep_num=2, ep_id="e2")])
        assert len(store) == 2


class TestReplace:
    def test_overwrites_all(self, store):
        store.update([_ep("s1", ep_num=1, ep_id="e1"), _ep("s1", ep_num=2, ep_id="e2")])
        store.replace([_ep("s2", ep_num=1, ep_id="e3")])
        assert len(store) == 1
        assert store.series_summaries()[0].series_id == "s2"

    def test_updates_last_sync(self, store):
        assert store.last_sync is None
        store.replace([_ep()])
        assert store.last_sync is not None


class TestLen:
    def test_len_counts_episodes(self, store):
        store.update([_ep("s1", ep_num=1, ep_id="e1"), _ep("s1", ep_num=2, ep_id="e2")])
        assert len(store) == 2
