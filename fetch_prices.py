"""Fetch daily closes from Yahoo Finance's public chart endpoint and cache them as JSON.

No API key. Be polite: this fetches once per ticker and caches. Cache format:
{"AAPL": [["2022-09-29", 142.48], ...], "SPY": [...]}
"""
from __future__ import annotations

import json
import os
import time
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

UA = {"User-Agent": "Mozilla/5.0 (senator-excess-return; educational)"}


def _fetch(ticker: str, start: date) -> list[tuple[str, float]]:
    p1 = int(datetime(start.year, start.month, start.day, tzinfo=timezone.utc).timestamp())
    p2 = int(time.time())
    q = urllib.parse.urlencode({"period1": p1, "period2": p2, "interval": "1d"})
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{urllib.parse.quote(ticker)}?{q}"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        j = json.load(r)
    res = j["chart"]["result"][0]
    ts, closes = res["timestamp"], res["indicators"]["quote"][0]["close"]
    return [(datetime.fromtimestamp(t, tz=timezone.utc).date().isoformat(), c)
            for t, c in zip(ts, closes) if c is not None]


def load_prices(cache_path: str, tickers: list[str], start: date) -> dict[str, list[tuple[date, float]]]:
    """Return {ticker: sorted [(date, close), ...]}, fetching anything missing from the cache."""
    cache: dict = {}
    if os.path.exists(cache_path):
        with open(cache_path) as f:
            cache = json.load(f)
    missing = [t for t in tickers if t not in cache]
    for i, t in enumerate(missing, 1):
        try:
            cache[t] = _fetch(t, start - timedelta(days=7))
            print(f"fetched {t} ({i}/{len(missing)})")
        except Exception as e:  # delisted, renamed, or rate-limited: skip, don't crash
            print(f"skip {t}: {e}")
            cache[t] = []
        time.sleep(0.3)
    if missing:
        with open(cache_path, "w") as f:
            json.dump(cache, f)
    return {t: sorted((date.fromisoformat(d), c) for d, c in rows) for t, rows in cache.items()}
