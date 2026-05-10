from __future__ import annotations

import datetime as dt


def today() -> dt.date:
    """Return the current date in the UTC timezone."""
    return dt.datetime.now(tz=dt.UTC).date()


__all__ = ["today"]