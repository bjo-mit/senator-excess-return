#!/usr/bin/env python3
"""Rank members of Congress by the realized excess return of mirroring their stock purchases.

Method
------
* Senate purchases only, filed within MAX_FILING_LAG_DAYS of the trade.
* Each trade is held HOLD_DAYS (366 = long-term capital gains threshold).
* Excess return = stock return minus SPY return over the identical window, from daily closes.
* Only *matured* trades are scored: the exit date must be in the past.
* A member is ranked only with at least MIN_TRADES matured trades.
* ``--persistence`` splits each member's record in half by date and reports how well the
  first half predicts the second. (In our data: r = 0.08, r^2 = 0.006. It does not.)

Input: a CSV of trades with columns  name, chamber, transaction, traded, filed, ticker
(dates as YYYY-MM-DD). See example_trades.csv. Prices are fetched from Yahoo Finance by
fetch_prices.py and cached in prices.json.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta

from fetch_prices import load_prices

HOLD_DAYS = 366
MAX_FILING_LAG_DAYS = 30
MIN_TRADES = 5
PRICE_TOLERANCE_DAYS = 7     # nearest close on or after the target date, within a week
BACKSTOP_AVOID = -15.0       # avg excess at or below this ...
BACKSTOP_MIN_TRADES = 30     # ... on at least this many trades => avoid


def parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def price_on_or_after(series: list[tuple[date, float]], target: date) -> float | None:
    """First close on or after `target`, if it is within PRICE_TOLERANCE_DAYS."""
    i = bisect.bisect_left(series, (target, -1.0))
    if i >= len(series):
        return None
    d, close = series[i]
    return close if (d - target).days <= PRICE_TOLERANCE_DAYS else None


def excess_return(series: list, spy: list, entry: date) -> float | None:
    exit_ = entry + timedelta(days=HOLD_DAYS)
    e, x = price_on_or_after(series, entry), price_on_or_after(series, exit_)
    se, sx = price_on_or_after(spy, entry), price_on_or_after(spy, exit_)
    if None in (e, x, se, sx) or e <= 0 or se <= 0:
        return None
    return (x / e - 1) * 100 - (sx / se - 1) * 100


def load_trades(path: str) -> list[dict]:
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    keep = []
    for r in rows:
        if not r["chamber"].lower().startswith("sen"):
            continue
        if not r["transaction"].lower().startswith("purchase"):
            continue
        traded, filed = parse_date(r["traded"]), parse_date(r["filed"])
        if (filed - traded).days > MAX_FILING_LAG_DAYS:
            continue
        keep.append({"name": r["name"].strip(), "ticker": r["ticker"].strip().upper(), "traded": traded})
    return keep


def score_trades(trades: list[dict], prices: dict) -> list[dict]:
    today = date.today()
    spy = prices.get("SPY", [])
    scored = []
    for tr in trades:
        if tr["traded"] + timedelta(days=HOLD_DAYS) > today:
            continue  # not matured
        ex = excess_return(prices.get(tr["ticker"], []), spy, tr["traded"])
        if ex is not None:
            scored.append({**tr, "excess": ex})
    return scored


def rank(scored: list[dict]) -> list[dict]:
    by_member: dict[str, list[dict]] = defaultdict(list)
    for s in scored:
        by_member[s["name"]].append(s)
    out = []
    for name, ts in by_member.items():
        if len(ts) < MIN_TRADES:
            continue
        ex = [t["excess"] for t in ts]
        avg = statistics.fmean(ex)
        out.append({
            "name": name, "n": len(ts), "avg_excess": round(avg, 2),
            "win_rate": round(100 * sum(e > 0 for e in ex) / len(ex)),
            "backstop_avoid": avg <= BACKSTOP_AVOID and len(ts) >= BACKSTOP_MIN_TRADES,
        })
    out.sort(key=lambda r: r["avg_excess"], reverse=True)
    q = max(1, len(out) // 4)
    for i, r in enumerate(out):
        r["top_quartile"] = i < q
    return out


def persistence(scored: list[dict], min_trades: int = 12) -> dict:
    """Does a member's first-half average excess predict the second half?"""
    by_member: dict[str, list[dict]] = defaultdict(list)
    for s in scored:
        by_member[s["name"]].append(s)
    firsts, seconds, flips = [], [], 0
    for ts in by_member.values():
        if len(ts) < min_trades:
            continue
        ts.sort(key=lambda t: t["traded"])
        half = len(ts) // 2
        a = statistics.fmean(t["excess"] for t in ts[:half])
        b = statistics.fmean(t["excess"] for t in ts[half:])
        firsts.append(a); seconds.append(b); flips += (a > 0) != (b > 0)
    n = len(firsts)
    if n < 3:
        return {"members": n, "note": "too few members with enough trades"}
    r = statistics.correlation(firsts, seconds)
    return {"members": n, "r": round(r, 3), "r_squared": round(r * r, 3), "sign_flips": flips}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("trades_csv")
    ap.add_argument("--prices", default="prices.json", help="price cache written by fetch_prices.py")
    ap.add_argument("--persistence", action="store_true", help="also run the first-half/second-half test")
    ap.add_argument("--out", default="rankings.json")
    args = ap.parse_args()

    trades = load_trades(args.trades_csv)
    prices = load_prices(args.prices, sorted({t["ticker"] for t in trades} | {"SPY"}),
                         start=min(t["traded"] for t in trades))
    scored = score_trades(trades, prices)
    ranked = rank(scored)

    print(f"{len(trades)} qualifying Senate purchases, {len(scored)} matured and priced, {len(ranked)} members ranked\n")
    print(f"{'Member':<28}{'Avg excess':>11}{'Trades':>8}{'Win':>6}  Flags")
    for r in ranked:
        flags = ("TOP " if r["top_quartile"] else "") + ("AVOID" if r["backstop_avoid"] else "")
        print(f"{r['name']:<28}{r['avg_excess']:>+10.1f}%{r['n']:>8}{r['win_rate']:>5}%  {flags}")
    result = {"evaluated": date.today().isoformat(), "hold_days": HOLD_DAYS, "min_trades": MIN_TRADES, "rankings": ranked}
    if args.persistence:
        result["persistence"] = persistence(scored)
        print("\nPersistence test (first half vs second half of each member's record):", result["persistence"])
    with open(args.out, "w") as f:
        json.dump(result, f, indent=2, default=str)
    print(f"\nWrote {args.out}")


if __name__ == "__main__":
    main()
