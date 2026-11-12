# Agensi listing copy

Paste these into the submit form at agensi.io/dashboard/submit. Upload `dist/daily-us-stock-analysis.zip`
(build it with `python3 tools/agensi_build.py`, which also checks this file against Agensi's field limits).
Logo and screenshots are in `agensi/media/`.

| Field | Value |
|---|---|
| Title | Daily US Stock Analysis: Scored Bias and Risk-Sized Plan |
| Categories | Trading & Investing; Research & Analysis; Finance & Accounting |
| Suggested price | $9 one-time |
| Tags | stocks, technical-analysis, trading, watchlist, risk-management |
| Compatibility note | Requires Python 3.10+ and internet access to api.nasdaq.com. No API key, no packages. |
| Permissions | Terminal (runs one Python script from a temporary file); network access to api.nasdaq.com only. Reads no local files, writes no files, uses no environment variables. |
| Docs link | https://github.com/FinnTech3/Daily_StocK_Analysis |

## Summary

Turn any US ticker into a scored, explained bias and a risk-sized trade plan in one run. No API key, no installs.

## Description

Ask your agent "how does AAPL look?" and get a straight answer you can check.

The skill scores any US stock or ETF from -100 to +100 on live daily prices and shows the reason behind every
point: trend, momentum, volume, strength against the S&P 500 and the market backdrop. For a bullish or lean bullish ticker it
adds a reference plan with an entry, a stop, two targets and the number of shares that fits your account and
your risk per trade. Ask about a whole watchlist and it returns one ranked table.

**How it works.** A bundled Python script downloads daily prices from Nasdaq's public quote API, computes the
indicators (moving averages, MACD, RSI, ATR, volume and relative strength against SPY), and returns JSON. Your
agent turns that JSON into the answer. The agent never does the maths, so the same ticker gives the same
numbers every time.

**What makes it different**

- Explained, not a black box: each factor comes with its points and a plain-English reason.
- Honest about risk: a neutral or bearish ticker gets no plan. Stale data, short history and possible splits are
  flagged instead of hidden.
- Nothing to set up: one self-contained script, standard library only, no API key, no account.

**Where it stops.** Daily technical analysis of US-listed stocks and ETFs only. No intraday data, options,
crypto, earnings, news or fundamentals, and no short-side plans. For education and research only, not financial
advice.

## See it in action

**Request:** "Check AAPL, MSFT, NVDA and TSLA. I have $25,000 and risk 1% a trade."

**Result:**

**Market: neutral.** SPY is above its 200-day average, but its 20-day volatility is 22% a year.

| Symbol | Bias | Score | Close | Entry | Stop | Target 1 |
|---|---|---:|---:|---:|---:|---:|
| AAPL | Bullish | +80 | $356.27 | $356.27 | $339.84 | $380.92 |
| TSLA | Lean bullish | +40 | $390.22 | $390.22 | $356.80 | $440.35 |
| MSFT | Lean bullish | +24 | $523.88 | $523.88 | $493.44 | $569.53 |
| NVDA | Bearish | -65 | $162.85 | - | - | - |

Prices are the close on 2026-11-13.

**AAPL: Bullish (+80)**
- Trend +40: above its 20-day ($346.15), 50-day ($339.04) and 200-day ($301.25) averages.
- Momentum +25: MACD histogram positive and rising, RSI 61.
- Relative strength +15: up 16.6% over 63 sessions against -2.4% for the S&P 500.
- Levels: support $325.33, resistance $360.83, 52-week range $243.42 to $360.83.
- Reference plan: entry $356.27, stop $339.84, targets $380.92 and $405.57. Entry at the last close. Sized for your risk: 15 shares ($5,344.05).

**TSLA: Lean bullish (+40)**
- Trend +30: above all three averages, though the 50-day is still below the 200-day.
- Relative strength +15: up 15.0% against -2.4% for the S&P 500.
- Momentum -5: MACD histogram negative but rising, RSI 54.
- Levels: support $338.15, resistance $414.23, 52-week range $297.38 to $498.83.
- Reference plan: entry $390.22, stop $356.80, targets $440.35 and $490.48. Entry at the last close. Sized for your risk: 7 shares ($2,731.54).

**MSFT: Lean bullish (+24)**
- Trend +24: above its 50-day ($519.00) and 200-day ($441.42) averages, below its 20-day ($529.39).
- Relative strength +15: up 9.1% against -2.4% for the S&P 500.
- Momentum -15: MACD histogram negative and falling, RSI 49.
- Levels: support $504.96, resistance $559.15, 52-week range $349.20 to $559.15.
- Reference plan: entry $523.88, stop $493.44, targets $569.53 and $615.19. Entry at the last close. Sized for your risk: 8 shares ($4,191.04).

**NVDA: Bearish (-65)**
- Trend -30: below its 20-day ($198.69), 50-day ($214.65) and 200-day ($204.19) averages.
- Relative strength -15: down 27.6% against -2.4% for the S&P 500.
- Momentum -10: MACD histogram negative and rising, RSI 25 (oversold).
- Volume -10: 1.9 times average volume on a down day.
- Levels: support $148.80, resistance $222.19, 52-week range $148.80 to $243.37.
- No long setup: the bias is bearish. Wait for price to reclaim its averages.

No warnings or errors.

*For education and research only. Not financial advice. Indicators describe the past and do not predict returns. Prices come from Nasdaq's public data, are not adjusted for dividends, and can be delayed or wrong.*

## Limitations

- Daily bars only; prices are not adjusted for dividends.
- Technical analysis only: no earnings dates, news, valuation or fundamentals.
- US-listed stocks and ETFs only. Indexes such as the VIX are not supported; use an ETF such as SPY or QQQ.
- Long-side reference plans only.
- Prices come from Nasdaq's public quote endpoint, which is not a documented API: it can change, rate-limit or return gaps. When it fails the skill says so and never falls back to remembered prices. Data can be delayed or wrong, so check anything you act on.

## FAQ

**Do I need an API key or an account?** No. The script reads Nasdaq's public quote API.

**Does it place trades?** No. It only analyses and explains.

**Can it size a position?** Yes. Give your account size and the percent you risk per trade and it returns the
share count that keeps the loss at your stop within that risk.

**Why does a ticker get no plan?** Only a Bullish or Lean bullish bias gets a plan. A neutral or bearish ticker shows why instead.

**Which agents does it work with?** Any agent that supports SKILL.md and can run a Python script.

## Use cases

- Morning watchlist check with a ranked table
- Sizing a position from account size and risk per trade
- Reading whether the market backdrop is risk-on or risk-off
