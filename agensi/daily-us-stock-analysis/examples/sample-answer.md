# Sample answer

This is the answer format for the request "Check AAPL, MSFT, NVDA and TSLA. I have $25,000 and risk 1% a trade." Every number comes from `sample-output.json`, which is real script output from 15 November 2026 (closes of 13 November).

---

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
