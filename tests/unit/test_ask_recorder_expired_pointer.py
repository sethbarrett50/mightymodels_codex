"""An expired unpruned session pointer cannot receive newly recorded user decisions."""

from datetime import UTC, datetime, timedelta
import pytest
from mightymodels_core.session_pointers import POINTER_RETENTION, SessionPointer
from mightymodels_hooks.ask_recorder import current_pointer


class FixedClock:
    def __init__(self, instant: datetime) -> None:
        self.instant = instant

    def now(self) -> datetime:
        return self.instant


@pytest.mark.unit
def test_recorder_rejects_expired_session_pointer() -> None:
    now = datetime(2026, 11, 8, tzinfo=UTC)
    pointer = SessionPointer(
        kind='ticket', key='old-ticket', written_at=now - POINTER_RETENTION - timedelta(seconds=1)
    )
    assert current_pointer(pointer, FixedClock(now)) is None


@pytest.mark.unit
def test_recorder_accepts_live_session_pointer() -> None:
    now = datetime(2026, 11, 8, tzinfo=UTC)
    pointer = SessionPointer(
        kind='investigation',
        key='current-investigation',
        written_at=now - timedelta(days=1),
    )
    assert current_pointer(pointer, FixedClock(now)) is pointer


@pytest.mark.unit
def test_recorder_accepts_retention_boundary() -> None:
    now = datetime(2026, 11, 8, tzinfo=UTC)
    pointer = SessionPointer(kind='ticket', key='ticket', written_at=now - POINTER_RETENTION)
    assert current_pointer(pointer, FixedClock(now)) is pointer


@pytest.mark.unit
def test_recorder_has_no_fallback_for_missing_pointer() -> None:
    assert current_pointer(None, FixedClock(datetime(2026, 11, 8, tzinfo=UTC))) is None
