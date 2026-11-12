import math
import random
from datetime import date, timedelta

import pytest

END = date(2026, 11, 11)


def make_bars(kind: str = "up", n: int = 300, seed: int = 7, start: float = 100.0) -> dict:
    """Deterministic synthetic daily bars so tests never touch the network."""
    rng = random.Random(seed)
    drift = {"up": 0.0012, "down": -0.0012, "flat": 0.0}[kind]
    close, price = [], start
    for _ in range(n):
        price *= math.exp(drift + rng.gauss(0, 0.008))
        close.append(price)
    days, day = [], END
    while len(days) < n:
        if day.weekday() < 5:
            days.append(day)
        day -= timedelta(days=1)
    return {
        "date": days[::-1],
        "high": [c * 1.006 for c in close],
        "low": [c * 0.994 for c in close],
        "close": close,
        "volume": [float(rng.randint(900_000, 1_100_000)) for _ in range(n)],
    }


def nasdaq_rows(bars: dict) -> list[dict]:
    """The same bars in the shape Nasdaq's API returns: newest first, formatted strings."""
    rows = []
    for i in range(len(bars["close"]) - 1, -1, -1):
        rows.append(
            {
                "date": bars["date"][i].strftime("%m/%d/%Y"),
                "close": f"${bars['close'][i]:,.4f}",
                "high": f"${bars['high'][i]:,.4f}",
                "low": f"${bars['low'][i]:,.4f}",
                "open": f"${bars['close'][i]:,.4f}",
                "volume": f"{int(bars['volume'][i]):,}",
            }
        )
    return rows


@pytest.fixture
def up():
    return make_bars("up")


@pytest.fixture
def down():
    return make_bars("down")


@pytest.fixture
def flat():
    return make_bars("flat")
