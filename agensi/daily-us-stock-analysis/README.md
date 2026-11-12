# Daily US stock analysis

An agent skill that turns any US stock or ETF ticker into a scored, explained bias and a risk-sized reference plan.

## What you get

- A score from -100 to +100 for each ticker, with a named reason for every point.
- The market backdrop: risk-on, neutral or risk-off.
- Support, resistance and the 52-week range.
- For a bullish or lean bullish ticker, an entry, a stop, two targets and a share count sized to your account and risk.
- A ranked table when you ask about several tickers.

## What it needs

- Python 3.10 or newer. No packages to install and no API key.
- Internet access to Nasdaq's public quote API, which is the only network call.
- Permission for your agent to run one Python script. The script reads no local files and writes none.

## How to use it

Ask your agent, for example:

- "How does AAPL look?"
- "Rank my watchlist: MSFT, NVDA, TSLA, BRK.B"
- "I have $25,000 and risk 1% a trade. Size a position in AAPL."
- "Is the market risk-on or risk-off?"

## Files

| File | Purpose |
|---|---|
| `SKILL.md` | The workflow the agent follows |
| `scripts/stock_analysis.py` | The analysis tool, one self-contained file |
| `references/scoring.md` | Every factor, weight and threshold |
| `examples/sample-output.json` | Real script output |
| `examples/sample-answer.md` | The answer format the agent follows |

## Limits

Prices come from Nasdaq's public quote endpoint, which is not a documented API and can change or rate-limit; the skill says so when it fails. Daily bars only. Technical analysis only: no earnings, news or fundamentals. US-listed stocks and ETFs only, no indexes. Long-side plans only. Prices are not adjusted for dividends.

For education and research only. Not financial advice.
