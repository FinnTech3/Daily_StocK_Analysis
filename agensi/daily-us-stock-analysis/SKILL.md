---
name: daily-us-stock-analysis
description: Scores US stocks and ETFs from -100 to +100 on live daily prices, explains every point, reads the market backdrop, and gives a risk-sized reference plan with entry, stop, targets and share count. Use when the user asks things like "how does AAPL look?", "rank my watchlist", "is NVDA strong or weak?", "where should the stop go?", "how many shares can I buy risking 1%?" or "is the market risk-on?". Do not use for intraday trading, options, crypto, non-US stocks, earnings, news or company fundamentals.
summary: Turn any US ticker into a scored, explained bias and a risk-sized trade plan in one run. No API key, no installs.
version: 1.0.0
tags: [stocks, technical-analysis, trading, watchlist, risk-management]
keywords: [stock analysis, technical analysis, position sizing, stop loss, market regime, watchlist scan, support and resistance]
use_cases:
  - Morning watchlist check with a ranked table
  - Sizing a position from account size and risk per trade
  - Reading whether the market backdrop is risk-on or risk-off
docs_url: https://github.com/FinnTech3/Daily_StocK_Analysis
---

# Daily US stock analysis

You analyse US stocks and ETFs with the bundled script `scripts/stock_analysis.py`, then explain the result in plain English. The script does all the maths. You never estimate a price, a level or a score yourself.

Requires: Python 3.10 or newer, and internet access to Nasdaq's public quote API (`api.nasdaq.com`). No API key, no packages.

## Requirements

- Python 3.10 or newer on the user's machine. Check with `python3 --version`. If it is missing, say so and stop.
- Network access. The script makes one kind of network call: it downloads daily prices from Nasdaq's public quote API (`api.nasdaq.com`). It reads no local files, writes no files and uses no environment variables.
- Nothing to install. The script uses the Python standard library only.

## Running the script

The script `scripts/stock_analysis.py` is delivered with this skill as text. Load it with `get_skill` using that file path, write it **unchanged** to a temporary file (for example in the system temp folder), run it with `python3`, and delete the file afterwards. Never save it into the project or a skills folder, and never retype, shorten or edit it. If the skill folder is already on disk, run it from there instead. Below, `$SCRIPT` stands for the path you ran it from.

## Workflow

1. **Collect the inputs.** You need one or more US tickers. Account size and risk per trade are optional. Pass `--account` only when the user gave an account size, and never guess one. If they gave no risk percent, the default is 1: say you used 1%. Never invent a ticker from a company name you are unsure of: ask. Pass tickers separated by spaces; commas also work.
2. **Run the script.**

   ```sh
   python3 "$SCRIPT" analyze AAPL MSFT BRK.B --json
   python3 "$SCRIPT" analyze NVDA --account 25000 --risk 1 --json
   python3 "$SCRIPT" market --json
   ```

   One call handles many tickers and includes the market regime, so run `market` only when the user asked just about the market. `--risk` is the percent of the account risked per trade (default 1, maximum 10).
3. **Read the JSON.** Fields: `regime` (label and reasons), `analyses[]` (`symbol`, `as_of`, `close`, `score`, `bias`, `factors[]`, `levels`, `plan`, `no_plan_reason`, `warnings[]`), `errors` (ticker to reason), `disclaimer`. `references/scoring.md` explains every factor and threshold: load it when the user asks why a score is what it is.
4. **Write the answer** in the output format below.
5. **Check before sending.** Every number in your answer appears in the JSON. Every ticker the user asked about is in the table or in the errors. The disclaimer is the last line.

## Output format

Follow `examples/sample-answer.md`. In this order:

1. **Market**: one line with the regime label and its main reason.
2. **Table** (when there is more than one ticker), sorted by score, highest first: Symbol, Bias, Score, Close, Entry, Stop, Target 1. Use `-` where there is no plan.
3. **Per ticker**: the bias and score, the date from `as_of`, the two or three factors with the largest points and their reasons, then support, resistance and the 52-week range.
4. **Plan**: only when `plan` is not null. Give entry, stop, both targets and the plan's `note`. Give the share count and position value only when `shares` is a number above zero. When `plan` is null, give `no_plan_reason` instead.
5. **Warnings and errors**: every item in `warnings` and `errors`, stated plainly.
6. **Disclaimer**: the `disclaimer` text, word for word.

## Edge cases

| Situation | What to do |
|---|---|
| Exit code 1 | Some tickers failed. Report the good ones and list `errors`. |
| Exit code 2 | Nothing succeeded or the input was bad. Give the reason from `errors` or the error line and ask for a corrected ticker. |
| "no price data ... check the ticker" | The ticker is wrong, delisted or not US-listed. Do not substitute another one. If every ticker, including a well-known one, gives this, Nasdaq's undocumented endpoint has probably changed: say so. |
| "unexpected reply" or "reply was not JSON" | Nasdaq's undocumented endpoint changed, blocked the request or sent something unreadable. Say that the data source is not working, and do not fall back to prices from memory. |
| "could not fetch ... after 3 tries" | Network or data-source problem. Say so and offer to retry later. Do not fall back to prices from memory. |
| Regime `unknown` | Say the market read failed and give the reason from `regime.reasons`. Scores then leave out the market-regime and relative-strength factors, so say they are less complete. `market` alone exits 1. |
| Warning "latest bar is N days old" | Tell the user the data is stale before anything else. |
| Warning "possible split or bad data" | Tell the user the levels may be distorted and should be checked. |
| Warning about short history | Say the 200-day average or the 52-week range is incomplete. |
| Class shares | Write them with a dot: `BRK.B`. The script also accepts `BRK-B`. |
| Indexes such as the VIX or the S&P 500 index | Not supported. Use an ETF such as `SPY` or `QQQ`. |
| The user wants a short-side plan | The script gives long-side plans only. Say so. Do not build one yourself. |

## Rules

- Present results as analysis, never as a recommendation or a promise. Say "bias", "reference plan" and "levels". Do not say "buy now", "sell now" or "guaranteed".
- Only a Bullish or Lean bullish bias has a plan. Never invent a plan for a neutral or bearish ticker.
- Never add facts about the company, its earnings or the news. This skill only knows price and volume.
- Never change, shorten or rewrite the script, and never report numbers the script did not produce.
- Always include the as-of date and the disclaimer.
