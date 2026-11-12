# How the score works

The score is the sum of the factors below, rounded and limited to the range -100 to +100. Each factor appears in the JSON as `factors[]` with its points and reason.

## Factors

| Factor | Points | Rule |
|---|---:|---|
| Trend | -40 to +40 | Price above or below the 20-day (8), 50-day (10) and 200-day (12) averages. Plus 5 each when the 20-day is above the 50-day and the 50-day is above the 200-day, minus 5 when below. A missing average is skipped. |
| Momentum | -25 to +25 | MACD histogram (12, 26, 9) positive +10 or negative -10. Rising against three sessions ago +5, falling -5. RSI(14): 55 to 70 "healthy" +10; 45 to 55 "neutral" 0; 30 to 45 "weak" -10; 70 and up "stretched" -5; under 30 "oversold" -5. |
| Volume | -10, 0 or +10 | Latest volume at least 1.2 times the average of the 20 sessions before it: +10 on an up day, -10 on a down day. Otherwise 0. |
| Relative strength | -15 to +15 | The ticker's return over 63 sessions minus SPY's return. A gap of 10 percentage points or more earns the full 15. Smaller gaps scale in proportion. |
| Extension | -8 or absent | Price more than 3 ATR(14) above the 20-day average. |
| Market regime | +5, 0 or -15 | Risk-on +5, neutral 0, risk-off -15. Absent when zero. |

## Bias labels

| Score | Bias |
|---:|---|
| 55 and up | Bullish |
| 20 to 54 | Lean bullish |
| -19 to 19 | Neutral |
| -54 to -20 | Lean bearish |
| -55 and below | Bearish |

## Market regime

Read from SPY, the S&P 500 ETF.

| Regime | Rule |
|---|---|
| Risk-off | SPY below its 200-day average, or its 20-day volatility at 28% a year or more |
| Risk-on | SPY above its 50-day, the 50-day above the 200-day, and volatility under 16% a year |
| Neutral | Anything else |
| Unknown | SPY data could not be fetched, or under 200 sessions of history |

Volatility is the annualised standard deviation of the last 20 daily log returns.

## Reference plan

Only for a Bullish or Lean bullish bias.

| Level | Rule |
|---|---|
| Entry | The last close. When the Extension factor fired, the 20-day average instead: the plan waits for a pullback, so its targets can sit below the current price. |
| Stop | Entry minus 2 ATR(14) |
| Target 1 | Entry plus 1.5 times the risk per share |
| Target 2 | Entry plus 3 times the risk per share |
| Shares | Account times risk percent, divided by the risk per share, rounded down, and never more than the account can buy |

## Warnings

| Warning | Meaning |
|---|---|
| Under 200 sessions of history | The 200-day average was skipped, so Trend can reach only 28 |
| Under 240 sessions | The 52-week range covers less than a year |
| Latest bar is N days old | More than 5 calendar days since the last bar |
| Price jumped over 45% in a day | Possible stock split or bad data; levels may be distorted |

## Data

Daily bars from Nasdaq's public quote API, about 420 calendar days back. Prices are not adjusted for dividends. Analysis needs at least 60 sessions.
