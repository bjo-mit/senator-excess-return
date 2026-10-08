# senator-excess-return

Rank members of Congress by the **realized** excess return of mirroring their stock purchases, and test whether that ranking predicts anything.

This is a small, self-contained version of the ranking module from a larger system I designed and co-built in 2026 that tracks STOCK Act disclosures, filters them, and alerts on qualifying trades. The larger system runs privately; this repo contains the part that is safe to publish and easy to read.

## What it does

1. Reads a CSV of congressional trades (member, chamber, transaction, trade date, filing date, ticker).
2. Keeps **Senate purchases filed within 30 days** of the trade.
3. Fetches daily closes from Yahoo Finance (no key needed) and caches them.
4. Scores each trade on **366-day excess return versus SPY**, computed from prices, counting **only matured trades** (the exit date must have passed).
5. Ranks members with at least 5 matured trades, flags the top quartile, and applies a disaster backstop (average excess at or below −15% on 30+ trades).
6. With `--persistence`, splits each member's record in half by date and reports how well the first half predicts the second.

## Why it is built this way

- **Compute your own returns.** The data vendor supplies an "excess return" field. In a 106,870-row sample, 31% of its values were below −100%, which is impossible for a long position. So the script prices every trade itself.
- **Score only matured trades.** Mixing trades that are 60 days old with trades that are 400 days old biases every average. In our data, immature Senate purchases averaged −3 to −5% while matured ones averaged +9.9%.
- **Test the ranking before trusting it.** In the full 12-year dataset, a senator's first-half average excess had a correlation of **+0.08** with the second half (r² = 0.006), and 16 of 34 senators flipped sign. The ranking was noise at these sample sizes: with a 45.5% trade-level standard deviation, a member judged on 15 trades has a ±11.7-point standard error. The durable edge in the larger system turned out to be in trade-level filters (beaten-down entry, low lobbying exposure, high beta), not in picking senators. The `--persistence` flag is here so anyone can check this on their own data.

## Usage

```bash
python3 rank_senators.py example_trades.csv --persistence
```

`example_trades.csv` is a 12-row file that shows the schema; the names are placeholders. Real disclosures are public record and available from the Senate Office of Public Records (eFD), the House Clerk, or aggregators such as Quiver Quant (API key required). Export them to the same six columns and point the script at the file.

Sample output:

```
10 qualifying Senate purchases, 10 matured and priced, 2 members ranked

Member                       Avg excess  Trades   Win  Flags
Senator A                        +63.5%       5   80%  TOP
Senator B                        -35.1%       5    0%
```

(Run 2026-09-28. Senator A's example trades are semiconductors and banks; Senator B's are energy. The gap is the sector story from the full dataset in miniature, and the persistence test needs more members than the example file has.)

Requires Python 3.10+. Standard library only.

## Files

- `rank_senators.py` — filtering, scoring, ranking, persistence test
- `fetch_prices.py` — Yahoo Finance daily closes with a JSON cache
- `example_trades.csv` — schema example

## Authorship

Designed by Blake O'Donnell (MIT '30). The larger system was built with a collaborator, using Claude Code as a coding assistant; the idea, the return definition, the maturity rule, and the persistence test were mine. This standalone version was extracted and simplified from it.

## License

MIT
