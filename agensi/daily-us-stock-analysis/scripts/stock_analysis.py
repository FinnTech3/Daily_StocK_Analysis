#!/usr/bin/env python3
"""US stock analysis in one file. Python 3.10+, standard library only, no API key.

    python3 stock_analysis.py market | analyze AAPL MSFT BRK.B [--account 25000 --risk 1] [--json]

Downloads daily prices from Nasdaq's public quote API (its only network call) and scores
each ticker from -100 to +100. Reads no local files, writes none, uses no environment variables.
Exit codes: 0 all tickers analysed, 1 some failed, 2 none succeeded or bad input.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta

__version__ = "1.0.0"

API = "https://api.nasdaq.com/api/quote/{symbol}/historical"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
}
LOOKBACK_DAYS = 420  # calendar days: enough for a 200-day average and a 52-week range
MIN_BARS = 60
RS_WINDOW = 63  # about three months of sessions
STALE_DAYS = 5
DISCLAIMER = (
    "For education and research only. Not financial advice. Indicators describe the past and "
    "do not predict returns. Prices come from Nasdaq's public data, are not adjusted for "
    "dividends, and can be delayed or wrong."
)
UNDOCUMENTED = "Nasdaq's quote endpoint is undocumented: it may be down, rate-limiting or changed."
_SYMBOL = re.compile(r"^[A-Z]{1,5}(?:\.[A-Z]{1,2})?$")


class DataError(Exception):
    """Market data could not be fetched or is unusable."""


def normalize_symbol(raw: str) -> str:
    """'brk-b' -> 'BRK.B'. Raises DataError for anything that is not a US-style ticker."""
    sym = raw.strip().upper().replace("/", ".").replace("-", ".")
    if not _SYMBOL.match(sym):
        raise DataError(f"'{raw}' is not a valid US ticker")
    return sym


def _number(text) -> float | None:
    try:
        value = float(str(text).replace("$", "").replace(",", ""))
    except ValueError:
        return None
    return value if abs(value) < 1e12 else None  # "nan", "inf" and absurd values are bad data


def parse_rows(rows: list[dict]) -> dict[str, list]:
    """Turn Nasdaq rows (newest first, strings) into ascending columns of numbers."""
    bars = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        close = _number(row.get("close"))
        try:
            day = datetime.strptime(str(row.get("date")), "%m/%d/%Y").date()
        except ValueError:
            continue
        if close is None or close <= 0:
            continue
        high, low = _number(row.get("high")) or close, _number(row.get("low")) or close
        bars.append((day, max(high, close), min(low, close), close, _number(row.get("volume")) or 0.0))
    bars = sorted({b[0]: b for b in bars}.values())
    return {k: [b[i] for b in bars] for i, k in enumerate(("date", "high", "low", "close", "volume"))}


def _request(symbol: str, asset: str, today: date, opener) -> dict:
    start = (today - timedelta(days=LOOKBACK_DAYS)).isoformat()
    query = urllib.parse.urlencode({"assetclass": asset, "fromdate": start, "todate": today.isoformat(), "limit": 500})
    url = API.format(symbol=urllib.parse.quote(symbol)) + "?" + query
    with opener(urllib.request.Request(url, headers=HEADERS), timeout=20) as resp:
        return json.loads(resp.read(5_000_000))  # a year is ~60 KB


def fetch_history(
    symbol: str, *, retries: int = 3, backoff: float = 1.0, sleep=time.sleep, opener=None, today=None
) -> dict[str, list]:
    """Daily bars for a stock or ETF. Network errors retry; an unknown ticker does not."""
    symbol = normalize_symbol(symbol)
    opener = opener or urllib.request.urlopen
    today = today or date.today()
    last_error = ""
    for attempt in range(retries):
        try:
            for asset in ("stocks", "etf"):
                payload = _request(symbol, asset, today, opener)
                rows = ((payload.get("data") or {}).get("tradesTable") or {}).get("rows") or []
                if rows:
                    bars = parse_rows(rows)
                    if bars["close"]:
                        return bars
            raise DataError(
                f"no price data for {symbol}; check the ticker. "
                "If all tickers say this, Nasdaq's endpoint may have changed."
            )
        except (AttributeError, TypeError):
            raise DataError(f"Nasdaq sent an unexpected reply for {symbol}. {UNDOCUMENTED}") from None
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
            last_error = str(getattr(exc, "reason", exc)) or type(exc).__name__
            if isinstance(exc, ValueError):
                last_error = "reply was not JSON (blocked?)"
            if attempt < retries - 1:
                sleep(backoff * 2**attempt)
    raise DataError(f"could not fetch {symbol} after {retries} tries: {last_error}. {UNDOCUMENTED}")


def fetch_many(symbols: list[str], fetch=fetch_history, max_workers: int = 4) -> dict:
    """Fetch several symbols in parallel. One bad symbol never sinks the batch."""

    def one(sym: str):
        try:
            return fetch(sym)
        except Exception as exc:
            return exc if isinstance(exc, DataError) else DataError(f"{sym}: unexpected error: {exc}")

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        return dict(zip(symbols, pool.map(one, symbols), strict=True))


def sma(xs: list[float], n: int) -> float | None:
    return sum(xs[-n:]) / n if len(xs) >= n else None


def _ewm(xs: list[float], alpha: float) -> list[float]:
    out, value = [], xs[0]
    for x in xs:
        value = alpha * x + (1 - alpha) * value
        out.append(value)
    return out


def rsi(closes: list[float], n: int = 14) -> float | None:
    """Wilder's RSI. A flat series reads 50; an unbroken rally reads 100."""
    if len(closes) <= n:
        return None
    diffs = [b - a for a, b in zip(closes, closes[1:], strict=False)]
    up = _ewm([max(d, 0.0) for d in diffs], 1 / n)[-1]
    down = _ewm([max(-d, 0.0) for d in diffs], 1 / n)[-1]
    if down == 0:
        return 50.0 if up == 0 else 100.0
    return 100 - 100 / (1 + up / down)


def macd_hist(closes: list[float], fast: int = 12, slow: int = 26, signal: int = 9) -> list[float]:
    """MACD histogram, valid from the bar where the signal line has enough history."""
    if len(closes) < slow + signal:
        return []
    line = [f - s for f, s in zip(_ewm(closes, 2 / (fast + 1)), _ewm(closes, 2 / (slow + 1)), strict=True)]
    line = line[slow - 1 :]
    sig = _ewm(line, 2 / (signal + 1))
    return [m - s for m, s in zip(line, sig, strict=True)][signal - 1 :]


def atr(bars: dict[str, list], n: int = 14) -> float | None:
    """Wilder's average true range."""
    high, low, close = bars["high"], bars["low"], bars["close"]
    if len(close) < n:
        return None
    tr = [high[0] - low[0]]
    for i in range(1, len(close)):
        tr.append(max(high[i] - low[i], abs(high[i] - close[i - 1]), abs(low[i] - close[i - 1])))
    return _ewm(tr, 1 / n)[-1]


def relative_volume(volume: list[float], n: int = 20) -> float | None:
    """Latest volume divided by the average of the n sessions before it."""
    if len(volume) <= n:
        return None
    base = sum(volume[-n - 1 : -1]) / n
    return volume[-1] / base if base > 0 else None


def realized_vol(closes: list[float], n: int = 20) -> float | None:
    """Annualised volatility of the last n daily log returns."""
    if len(closes) <= n:
        return None
    rets = [math.log(b / a) for a, b in zip(closes[-n - 1 :], closes[-n:], strict=False)]
    mean = sum(rets) / n
    return math.sqrt(sum((r - mean) ** 2 for r in rets) / (n - 1)) * math.sqrt(252)


REGIME_POINTS = {"risk-on": 5, "neutral": 0, "risk-off": -15, "unknown": 0}


def classify_regime(spy: dict[str, list] | None) -> dict:
    """Market backdrop from SPY's trend and its own 20-day volatility."""
    if not spy or len(spy["close"]) < 200:
        return {"label": "unknown", "points": 0, "reasons": ["not enough S&P 500 history to judge"]}
    close = spy["close"]
    last, ma50, ma200, vol = close[-1], sma(close, 50), sma(close, 200), realized_vol(close)
    reasons = [
        f"S&P 500 (SPY) {'above' if last > ma200 else 'below'} its 200-day average",
        f"50-day average {'above' if ma50 > ma200 else 'below'} the 200-day",
        f"20-day volatility {vol:.0%} a year",
    ]
    if last < ma200 or vol >= 0.28:
        label = "risk-off"
    elif last > ma50 > ma200 and vol < 0.16:
        label = "risk-on"
    else:
        label = "neutral"
    return {"label": label, "points": REGIME_POINTS[label], "reasons": reasons, "spy_close": round(last, 2)}


def bias_label(score: int) -> str:
    for floor, label in ((55, "Bullish"), (20, "Lean bullish"), (-19, "Neutral"), (-54, "Lean bearish")):
        if score >= floor:
            return label
    return "Bearish"


def _side(a: float, b: float) -> int:
    return (a > b) - (a < b)


def analyze(symbol, bars, *, spy=None, regime=None, account=None, risk_pct=1.0, today=None) -> dict:
    """Score one ticker; every point is a named factor."""
    close = bars["close"]
    if len(close) < MIN_BARS:
        raise DataError(f"{symbol}: only {len(close)} sessions of history, need {MIN_BARS}+")
    price = close[-1]
    ma20, ma50, ma200 = sma(close, 20), sma(close, 50), sma(close, 200)
    atr14, rsi14, hist = atr(bars), rsi(close), macd_hist(close)
    factors = []

    def add(name, points, why):
        factors.append({"name": name, "points": points, "why": why})

    # Trend: where price sits against its averages, and how they stack (max +/-40)
    pts, notes = 0, []
    for label, ma, weight in (("20-day", ma20, 8), ("50-day", ma50, 10), ("200-day", ma200, 12)):
        if ma is not None:
            side = _side(price, ma)
            pts += weight * side
            notes.append(f"{('below', 'at', 'above')[side + 1]} {label} ({ma:,.2f})")
    for fast, slow in ((ma20, ma50), (ma50, ma200)):
        if fast is not None and slow is not None:
            pts += 5 * _side(fast, slow)
    add("Trend", pts, "; ".join(notes))

    # Momentum: MACD histogram, its direction, and the RSI zone (max +/-25)
    now, before = hist[-1], hist[-4]
    pts = 10 * _side(now, 0) + 5 * _side(now, before)
    zones = ((70, -5, "stretched"), (55, 10, "healthy"), (45, 0, "neutral"), (30, -10, "weak"), (0, -5, "oversold"))
    _, adjust, zone = next(z for z in zones if rsi14 >= z[0])
    pts += adjust
    direction = ("falling", "flat", "rising")[_side(now, before) + 1]
    sign = ("negative", "zero", "positive")[_side(now, 0) + 1]
    add("Momentum", pts, f"MACD histogram {sign} and {direction}; RSI {rsi14:.0f} ({zone})")

    # Volume: is the move backed by volume? (max +/-10)
    rvol, up_day = relative_volume(bars["volume"]), price >= close[-2]
    if rvol is not None and rvol >= 1.2:
        add("Volume", 10 if up_day else -10, f"{rvol:.1f}x average volume on {'an up' if up_day else 'a down'} day")
    else:
        add("Volume", 0, "no unusual participation")

    # Relative strength against the S&P 500 (max +/-15)
    if spy and len(close) > RS_WINDOW and len(spy["close"]) > RS_WINDOW:
        mine = price / close[-RS_WINDOW - 1] - 1
        market = spy["close"][-1] / spy["close"][-RS_WINDOW - 1] - 1
        pts = round(max(-1.0, min(1.0, (mine - market) / 0.10)) * 15, 1)
        add("Relative strength", pts, f"{mine:+.1%} vs S&P 500 {market:+.1%} over {RS_WINDOW} sessions")

    # Extension: a stretched trend tends to pull back
    extended = bool(atr14) and price > ma20 + 3 * atr14
    if extended:
        add("Extension", -8, "price is over 3 ATR above the 20-day average")

    regime = regime or {"label": "unknown", "points": 0}
    if regime["points"]:
        add("Market regime", regime["points"], f"{regime['label']} market")

    score = max(-100, min(100, round(sum(f["points"] for f in factors))))
    bias = bias_label(score)
    window = slice(-252, None)
    levels = {
        "support_20d": round(min(bars["low"][-20:]), 2),
        "resistance_20d": round(max(bars["high"][-20:]), 2),
        "high_52w": round(max(bars["high"][window]), 2),
        "low_52w": round(min(bars["low"][window]), 2),
        "sma_20": round(ma20, 2),
        "sma_50": round(ma50, 2),
        "sma_200": None if ma200 is None else round(ma200, 2),
        "atr_14": round(atr14, 2),
    }

    warnings = []
    if ma200 is None:
        warnings.append("under 200 sessions of history, so the 200-day average was skipped")
    if len(close) < 240:
        warnings.append(f"only {len(close)} sessions of history, so the 52-week range is shorter")
    age = ((today or date.today()) - bars["date"][-1]).days
    if age > STALE_DAYS:
        warnings.append(f"latest bar is {age} days old")
    jumps = [d for d, a, b in zip(bars["date"][1:], close, close[1:], strict=False) if abs(b / a - 1) > 0.45]
    if jumps:
        warnings.append(f"price jumped over 45% on {jumps[-1]}: possible split or bad data, treat levels with care")

    plan, no_plan = make_plan(price, ma20, atr14, bias, extended, account, risk_pct)
    return {
        "symbol": symbol,
        "as_of": bars["date"][-1].isoformat(),
        "close": round(price, 2),
        "score": score,
        "bias": bias,
        "regime": regime["label"],
        "factors": factors,
        "levels": levels,
        "plan": plan,
        "no_plan_reason": no_plan,
        "warnings": warnings,
    }


def make_plan(price, ma20, atr14, bias, extended, account, risk_pct):
    """Long-side levels, only for a bullish bias. Stop 2 ATR below entry; targets 1.5R and 3R."""
    if bias == "Neutral":
        return None, "the bias is neutral. Wait for a clearer trend"
    if bias not in ("Bullish", "Lean bullish"):
        return None, "the bias is bearish. Wait for price to reclaim its averages"
    entry = ma20 if extended else price
    risk = 2 * atr14
    if risk <= 0 or entry - risk <= 0:
        return None, "a valid stop could not be computed from this data"
    note = "Entry waits for a pullback to the 20-day average." if extended else "Entry at the last close."
    shares = value = None
    if account:
        shares = int(min((account * risk_pct / 100) // risk, account // entry))
        if shares < 1:
            note += " Account too small for one share at this risk."
        else:
            value = round(shares * entry, 2)
    plan = {
        "entry": round(entry, 2),
        "stop": round(entry - risk, 2),
        "target_1": round(entry + 1.5 * risk, 2),
        "target_2": round(entry + 3 * risk, 2),
        "risk_per_share": round(risk, 2),
        "shares": shares,
        "position_value": value,
        "note": note,
    }
    return plan, None


def _money(v) -> str:
    return "n/a" if v is None else f"${v:,.2f}"


def render_regime(regime: dict) -> str:
    return "\n".join([f"## Market regime: {regime['label'].title()}", ""] + [f"- {r}" for r in regime["reasons"]])


def render_one(a: dict) -> str:
    out = [f"## {a['symbol']}: {a['bias']} ({a['score']:+d})", ""]
    out += [f"Last close **{_money(a['close'])}** on {a['as_of']}. Market regime: {a['regime']}.", ""]
    out += ["| Factor | Points | Why |", "|---|---:|---|"]
    out += [f"| {f['name']} | {f['points']:+g} | {f['why']} |" for f in a["factors"]]
    lv = a["levels"]
    out += [
        "",
        f"**Key levels**: support {_money(lv['support_20d'])}, resistance {_money(lv['resistance_20d'])}, "
        f"52-week range {_money(lv['low_52w'])} to {_money(lv['high_52w'])}, "
        f"50-day {_money(lv['sma_50'])}, 200-day {_money(lv['sma_200'])}.",
        "",
    ]
    p = a["plan"]
    if p:
        out.append(
            f"**Reference plan (long)**: entry {_money(p['entry'])}, stop {_money(p['stop'])} "
            f"(risk {_money(p['risk_per_share'])}/share), targets {_money(p['target_1'])} and "
            f"{_money(p['target_2'])}. {p['note']}"
        )
        if p["shares"]:
            out.append(f"Sized for your risk: **{p['shares']} shares** ({_money(p['position_value'])}).")
    else:
        out.append(f"**No long setup**: {a['no_plan_reason']}.")
    return "\n".join(out + [""] + [f"> Warning: {w}" for w in a["warnings"]]).rstrip()


def render_markdown(results: list[dict], regime: dict, errors: dict[str, str]) -> str:
    parts = ["# Daily stock analysis", "", render_regime(regime), ""]
    ranked = sorted(results, key=lambda x: -x["score"])
    if len(results) > 1:
        parts += ["| Symbol | Bias | Score | Close | Entry | Stop | Target 1 |", "|---|---|---:|---:|---:|---:|---:|"]
        for a in ranked:
            p = a["plan"] or {}
            cells = [_money(p[k]) if p else "-" for k in ("entry", "stop", "target_1")]
            parts.append(
                f"| {a['symbol']} | {a['bias']} | {a['score']:+d} | {_money(a['close'])} | " + " | ".join(cells) + " |"
            )
        parts.append("")
    for a in ranked:
        parts += [render_one(a), ""]
    if errors:
        parts += ["## Could not analyze", ""] + [f"- **{s}**: {e}" for s, e in errors.items()] + [""]
    return "\n".join(parts + [f"*{DISCLAIMER}*"])


def market(fetch=fetch_history):
    """Return (regime, spy_bars). A failed fetch degrades to an 'unknown' regime."""
    try:
        spy = fetch("SPY")
    except DataError as exc:
        return {"label": "unknown", "points": 0, "reasons": [f"S&P 500 data unavailable: {exc}"]}, None
    return classify_regime(spy), spy


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="stock_analysis.py")
    p.add_argument("--version", action="version", version=f"stock_analysis {__version__}")
    sub = p.add_subparsers(dest="cmd")
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="machine-readable output")
    a = sub.add_parser("analyze", parents=[common], help="score tickers")
    a.add_argument("symbols", nargs="+", help="tickers such as AAPL MSFT BRK.B")
    a.add_argument("--account", type=float, help="account size in USD, for share counts")
    a.add_argument("--risk", type=float, default=1.0, help="percent of account risked per trade (max 10)")
    sub.add_parser("market", parents=[common], help="show the market regime")
    return p


def main(argv: list[str] | None = None, fetch=fetch_history) -> int:
    args = _parser().parse_args(argv)
    if args.cmd == "market":
        regime = market(fetch)[0]
        print(
            json.dumps({"regime": regime, "disclaimer": DISCLAIMER}, indent=2) if args.json else render_regime(regime)
        )
        return int(regime["label"] == "unknown")
    if args.cmd != "analyze":
        _parser().print_help()
        return 2
    if args.account is not None and not (math.isfinite(args.account) and args.account > 0):
        print("error: --account must be a positive number", file=sys.stderr)
        return 2
    if not (math.isfinite(args.risk) and 0 < args.risk <= 10):
        print("error: --risk must be between 0 and 10 percent", file=sys.stderr)
        return 2

    errors: dict[str, str] = {}
    symbols: list[str] = []
    for raw in (t for arg in args.symbols for t in re.findall(r"[^,\s]+", arg) or [arg]):
        try:
            sym = normalize_symbol(raw)
        except DataError as exc:
            errors[raw] = str(exc)
            continue
        if sym not in symbols:
            symbols.append(sym)

    regime, spy = market(fetch)
    results = []
    for sym, bars in fetch_many(symbols, fetch).items():
        try:
            if isinstance(bars, DataError):
                raise bars
            results.append(analyze(sym, bars, spy=spy, regime=regime, account=args.account, risk_pct=args.risk))
        except DataError as exc:
            errors[sym] = str(exc)

    if args.json:
        print(json.dumps({"regime": regime, "analyses": results, "errors": errors, "disclaimer": DISCLAIMER}, indent=2))
    else:
        print(render_markdown(results, regime, errors))
    if not results:
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(errors="replace")
    sys.exit(main())
