"""Persistent per-user write limits; never trust forwarded client IP headers."""

from datetime import datetime, timedelta, timezone

from backend.app.core.errors import RateLimitError
from backend.app.database.models import RateWindow
from sqlalchemy import delete


async def consume_write(db, owner_id, limit):
    now = datetime.now(timezone.utc)
    start = now.replace(minute=0, second=0, microsecond=0)
    if db.bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import insert
    else:
        from sqlalchemy.dialects.sqlite import insert
    statement = insert(RateWindow).values(owner_id=owner_id, window_start=start, count=1)
    statement = statement.on_conflict_do_update(
        index_elements=[RateWindow.owner_id, RateWindow.window_start],
        set_={"count": RateWindow.count + 1},
    ).returning(RateWindow.count)
    count = (await db.execute(statement)).scalar_one()
    await db.execute(delete(RateWindow).where(RateWindow.window_start < start - timedelta(hours=2)))
    await db.commit()
    if count > limit:
        raise RateLimitError("Hourly write limit reached. Please try again after the hour changes.")
