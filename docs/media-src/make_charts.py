#!/usr/bin/env python3
"""make_charts.py: fetch real data with the tool itself and write the HTML pages that render.mjs turns into images.

Usage: python3 make_charts.py OUT_DIR

Everything drawn comes from the live run: the factor points and the plan come from `stock_analysis.py ... --json`,
and the AAPL price line and its averages come from the same module's own fetch_history() and sma(). Nothing is typed in
by hand. The inputs are saved to chart-data.json next to this file so you can see what the images were drawn from.
"""

import html
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parents[1] / "agensi" / "daily-us-stock-analysis" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import stock_analysis as sa  # noqa: E402

TICKERS = ["AAPL", "MSFT", "NVDA", "TSLA"]
ACCOUNT = 25000
FACTOR_COLOURS = {
    "Trend": "#2563eb",
    "Momentum": "#b45309",
    "Volume": "#7c3aed",
    "Relative strength": "#047857",
    "Extension": "#be185d",
    "Market regime": "#475569",
}
BIAS_COLOURS = {
    "Bullish": "#047857",
    "Lean bullish": "#15803d",
    "Neutral": "#64748b",
    "Lean bearish": "#b91c1c",
    "Bearish": "#b91c1c",
}
FONT = "Inter, system-ui, -apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def collect() -> dict:
    cmd = [sys.executable, str(SCRIPTS / "stock_analysis.py"), "analyze", *TICKERS, "--account", str(ACCOUNT), "--json"]
    run = subprocess.run(cmd, capture_output=True, text=True, timeout=120, check=True)
    analysis = json.loads(run.stdout)
    bars = sa.fetch_history("AAPL")
    close = bars["close"]
    assert round(close[-1], 2) == next(a["close"] for a in analysis["analyses"] if a["symbol"] == "AAPL"), "data moved"
    first = 199  # the first bar that has a 200-day average
    rows = []
    for i in range(first, len(close)):
        rows.append(
            {
                "date": bars["date"][i].isoformat(),
                "close": round(close[i], 2),
                "sma20": round(sa.sma(close[: i + 1], 20), 2),
                "sma50": round(sa.sma(close[: i + 1], 50), 2),
                "sma200": round(sa.sma(close[: i + 1], 200), 2),
            }
        )
    return {"run_date": date.today().isoformat(), "account": ACCOUNT, "analysis": analysis, "aapl": rows}


def count_tests() -> int:
    run = subprocess.run([sys.executable, "-m", "pytest", "--collect-only", "-q"], cwd=HERE.parents[1],
                         capture_output=True, text=True, timeout=120, check=True)
    return int(next(ln for ln in run.stdout.splitlines() if " tests collected" in ln or " test collected" in ln).split()[0])


def answer_card(out: Path) -> None:
    """The listing screenshot: the real sample answer, with the TSLA and MSFT sections left out (and said so)."""
    text = (HERE.parents[1] / "agensi" / "daily-us-stock-analysis" / "examples" / "sample-answer.md").read_text()
    body = text.split("---\n", 1)[1]
    blocks = [b.strip() for b in body.split("\n\n")]
    keep, skip = [], False
    for b in blocks:
        if b.startswith(("**TSLA", "**MSFT")):
            skip = True
            continue
        skip = False if b.startswith(("**NVDA", "**AAPL")) else skip
        if not skip:
            keep.append(b)
    keep.insert(-1, "*TSLA and MSFT sections are left out of this image. The full answer is in examples/sample-answer.md.*")
    (out / "answer.md").write_text("\n\n".join(keep) + "\n")


def esc(text) -> str:
    return html.escape(str(text))


def page(body: str, width: int, height: int, bg: str = "#ffffff") -> str:
    return (
        f"<!doctype html><meta charset='utf-8'><style>*{{box-sizing:border-box}}"
        f"body{{margin:0;background:{bg};font-family:{FONT}}}</style>"
        f"<div id='frame' style='width:{width}px;height:{height}px;position:relative;overflow:hidden'>{body}</div>"
    )


def signed(v: float) -> str:
    return f"{v:+g}"


# ---------------------------------------------------------------- score anatomy


def anatomy_svg(data: dict, w: int = 1000, compact: bool = False) -> tuple[str, int]:
    """One row per ticker: its factors stacked either side of zero, with the net score marked."""
    results = sorted(data["analysis"]["analyses"], key=lambda a: -a["score"])
    left, right = (110 if compact else 150), w - 24
    scale = (right - left) / 200  # points to pixels, axis -100..+100
    row_h, top = (78 if compact else 112), (44 if compact else 138)
    bar_h = 30 if compact else 34
    body_h = row_h * len(results)
    height = top + body_h + (24 if compact else 100)

    def x0(pts: float) -> float:
        return left + (pts + 100) * scale

    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{height}' viewBox='0 0 {w} {height}'>"]
    bands = [(-100, -55, "#fee2e2", "Bearish"), (-55, -20, "#fef2f2", "Lean bearish"), (-20, 20, "#f1f5f9", "Neutral"),
             (20, 55, "#f0fdf4", "Lean bullish"), (55, 100, "#dcfce7", "Bullish")]
    for lo, hi, colour, label in bands:
        out.append(f"<rect x='{x0(lo):.1f}' y='{top - 20}' width='{(hi - lo) * scale:.1f}' height='{body_h + 10}' fill='{colour}'/>")
        if not compact:
            out.append(f"<text x='{(x0(lo) + x0(hi)) / 2:.1f}' y='{top - 30}' text-anchor='middle' font-size='12' "
                       f"fill='#64748b' font-weight='600'>{label}</text>")
    for pts in (-100, -55, -20, 0, 20, 55, 100):
        out.append(f"<line x1='{x0(pts):.1f}' x2='{x0(pts):.1f}' y1='{top - 20}' y2='{top + body_h - 10}' "
                   f"stroke='{'#334155' if pts == 0 else '#cbd5e1'}' stroke-width='{1.5 if pts == 0 else 1}'/>")
        if not compact:
            out.append(f"<text x='{x0(pts):.1f}' y='{top + body_h + 6}' text-anchor='middle' font-size='11' "
                       f"fill='#94a3b8'>{pts}</text>")
    for i, a in enumerate(results):
        y = top + i * row_h
        out.append(f"<text x='{16 if compact else 20}' y='{y + 22}' font-size='{22 if compact else 26}' font-weight='800' "
                   f"fill='#0f172a'>{esc(a['symbol'])}</text>")
        out.append(f"<text x='{16 if compact else 20}' y='{y + 44}' font-size='13' font-weight='700' "
                   f"fill='{BIAS_COLOURS[a['bias']]}'>{esc(a['bias'])}</text>")
        pos = neg = 0.0
        for f in a["factors"]:
            p = f["points"]
            if not p:
                continue
            start = pos if p > 0 else neg - abs(p)
            if p > 0:
                pos += p
            else:
                neg -= abs(p)
            x, width = x0(start), abs(p) * scale
            out.append(f"<rect x='{x:.1f}' y='{y}' width='{width:.1f}' height='{bar_h}' rx='3' "
                       f"fill='{FACTOR_COLOURS[f['name']]}' stroke='#fff' stroke-width='1.5'/>")
            if width >= (22 if compact else 34):
                out.append(f"<text x='{x + width / 2:.1f}' y='{y + bar_h / 2 + 5}' text-anchor='middle' "
                           f"font-size='{12 if compact else 14}' font-weight='700' fill='#fff'>{esc(signed(p))}</text>")
            elif not compact:  # too narrow for a label inside: put it above the segment
                out.append(f"<text x='{x + width / 2:.1f}' y='{y - 5}' text-anchor='middle' font-size='12' "
                           f"font-weight='700' fill='{FACTOR_COLOURS[f['name']]}'>{esc(signed(p))}</text>")
        mx = x0(a["score"])
        out.append(f"<path d='M{mx - 7:.1f},{y + bar_h + 12} L{mx + 7:.1f},{y + bar_h + 12} L{mx:.1f},{y + bar_h + 3} Z' "
                   f"fill='#0f172a'/>")
        out.append(f"<text x='{mx:.1f}' y='{y + bar_h + 32}' text-anchor='middle' font-size='{15 if compact else 17}' "
                   f"font-weight='800' fill='#0f172a'>{a['score']:+d}</text>")
    if not compact:
        lx, ly = 20, top + body_h + 34
        used = {f["name"] for a in results for f in a["factors"] if f["points"]}
        for name, colour in FACTOR_COLOURS.items():
            if name in used:
                out.append(f"<rect x='{lx}' y='{ly}' width='16' height='16' rx='3' fill='{colour}'/>")
                out.append(f"<text x='{lx + 24}' y='{ly + 13}' font-size='14' fill='#334155'>{esc(name)}</text>")
                lx += 64 + len(name) * 8
        out.append(f"<text x='20' y='{ly + 46}' font-size='13' fill='#64748b'>The black marker is the score: the positive "
                   f"and negative factors add up to it. The axis runs -100 to +100.</text>")
    out.append("</svg>")
    return "".join(out), height


def anatomy_page(data: dict) -> tuple[str, int, int]:
    w = 1000
    svg, h = anatomy_svg(data, w)
    regime = data["analysis"]["regime"]["label"]
    asof = data["analysis"]["analyses"][0]["as_of"]
    head = (
        f"<div style='position:absolute;left:20px;top:20px;right:20px'>"
        f"<div style='font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-.01em'>Four scores, taken apart</div>"
        f"<div style='font-size:14px;color:#475569;margin-top:6px'>Every segment is one named factor, in the "
        f"tool's own points. Daily closes to {esc(asof)}, market regime {esc(regime)}.</div></div>"
    )
    return page(head + f"<div style='position:absolute;left:0;top:0'>{svg}</div>", w, h), w, h


# ---------------------------------------------------------------- plan on a real chart


def plan_page(data: dict) -> tuple[str, int, int]:
    rows = data["aapl"]
    a = next(x for x in data["analysis"]["analyses"] if x["symbol"] == "AAPL")
    plan = a["plan"]
    w, h = 1000, 640
    pl, pt, pb = 70, 150, 90
    zone_start = 650  # price data ends here; the plan levels are drawn to its right
    ex = 790  # right edge of the plan zone
    n = len(rows)
    averages = (("sma200", "#64748b", "200-day"), ("sma50", "#b45309", "50-day"), ("sma20", "#7c3aed", "20-day"))
    series = [r[k] for r in rows for k in ("close", "sma20", "sma50", "sma200")]
    lo = min(min(series), plan["stop"]) - 8
    hi = max(max(series), plan["target_2"]) + 8

    def x_of(i: int) -> float:
        return pl + i * (zone_start - pl) / (n - 1)

    def y_of(v: float) -> float:
        return pt + (hi - v) / (hi - lo) * (h - pt - pb)

    out = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{w}' height='{h}' viewBox='0 0 {w} {h}'>"]
    tick = int(lo // 20 + 1) * 20
    while tick < hi:
        out.append(f"<line x1='{pl}' x2='{ex}' y1='{y_of(tick):.1f}' y2='{y_of(tick):.1f}' stroke='#e2e8f0'/>")
        out.append(f"<text x='{pl - 8}' y='{y_of(tick) + 4:.1f}' text-anchor='end' font-size='12' fill='#64748b'>${tick}</text>")
        tick += 20
    seen = set()
    for i, r in enumerate(rows):  # one label per month, at its first session
        if r["date"][:7] not in seen:
            seen.add(r["date"][:7])
            if x_of(i) > pl + 25:
                out.append(f"<text x='{x_of(i):.1f}' y='{h - pb + 22}' font-size='12' fill='#64748b'>"
                           f"{date.fromisoformat(r['date']):%b}</text>")
    last = x_of(n - 1)
    out.append(f"<rect x='{last:.1f}' y='{y_of(plan['entry']):.1f}' width='{ex - last:.1f}' "
               f"height='{y_of(plan['stop']) - y_of(plan['entry']):.1f}' fill='#fee2e2'/>")
    out.append(f"<rect x='{last:.1f}' y='{y_of(plan['target_2']):.1f}' width='{ex - last:.1f}' "
               f"height='{y_of(plan['entry']) - y_of(plan['target_2']):.1f}' fill='#dcfce7'/>")
    for key, colour, _ in averages:
        pts = " ".join(f"{x_of(i):.1f},{y_of(r[key]):.1f}" for i, r in enumerate(rows))
        out.append(f"<polyline points='{pts}' fill='none' stroke='{colour}' stroke-width='1.8'/>")
    pts = " ".join(f"{x_of(i):.1f},{y_of(r['close']):.1f}" for i, r in enumerate(rows))
    out.append(f"<polyline points='{pts}' fill='none' stroke='#0f172a' stroke-width='2.4' stroke-linejoin='round'/>")
    out.append(f"<circle cx='{last:.1f}' cy='{y_of(rows[-1]['close']):.1f}' r='5' fill='#0f172a'/>")
    levels = (
        (plan["target_2"], "#15803d", f"Target 2  ${plan['target_2']:,.2f}", "3R"),
        (plan["target_1"], "#15803d", f"Target 1  ${plan['target_1']:,.2f}", "1.5R"),
        (plan["entry"], "#0f172a", f"Entry  ${plan['entry']:,.2f}", "the last close"),
        (plan["stop"], "#b91c1c", f"Stop  ${plan['stop']:,.2f}", "2 ATR below entry"),
    )
    for value, colour, label, note in levels:
        y = y_of(value)
        dash = "" if colour == "#0f172a" else "6 4"
        out.append(f"<line x1='{last:.1f}' x2='{ex}' y1='{y:.1f}' y2='{y:.1f}' stroke='{colour}' stroke-width='2' "
                   f"stroke-dasharray='{dash}'/>")
        out.append(f"<text x='{ex + 10}' y='{y + 1:.1f}' font-size='14' font-weight='700' fill='{colour}'>{esc(label)}</text>")
        out.append(f"<text x='{ex + 10}' y='{y + 17:.1f}' font-size='12' fill='#64748b'>{esc(note)}</text>")
    out.append(f"<text x='{(last + ex) / 2:.1f}' y='{y_of(plan['target_2']) - 8:.1f}' text-anchor='middle' font-size='12' "
               f"fill='#64748b'>the plan, not a forecast</text>")
    lx = pl  # legend
    for label, colour in (("Daily close", "#0f172a"), ("20-day average", "#7c3aed"), ("50-day average", "#b45309"),
                          ("200-day average", "#64748b")):
        out.append(f"<line x1='{lx}' x2='{lx + 24}' y1='{pt - 22}' y2='{pt - 22}' stroke='{colour}' stroke-width='3'/>")
        out.append(f"<text x='{lx + 32}' y='{pt - 18}' font-size='13' fill='#334155'>{label}</text>")
        lx += 56 + len(label) * 7
    out.append("</svg>")
    shares, risk = plan["shares"], plan["risk_per_share"]
    head = (
        "<div style='position:absolute;left:20px;top:20px;right:20px'>"
        "<div style='font-size:26px;font-weight:800;color:#0f172a;letter-spacing:-.01em'>AAPL: the reference plan on its real chart</div>"
        f"<div style='font-size:14px;color:#475569;margin-top:6px'>Entry at the last close, stop 2 ATR below, targets at 1.5R and 3R. "
        f"Closes to {esc(a['as_of'])}.</div></div>"
    )
    foot = (
        "<div style='position:absolute;left:20px;bottom:16px;right:20px;font-size:15px;color:#0f172a'>"
        f"<b>{shares} shares</b> (${plan['position_value']:,.2f}): {shares} x ${risk:.2f} = ${shares * risk:,.2f} at risk if the "
        f"stop is hit, inside 1% of ${data['account']:,}.</div>"
    )
    return page(head + f"<div style='position:absolute;left:0;top:0'>{''.join(out)}</div>" + foot, w, h), w, h


# ---------------------------------------------------------------- social preview and listing cards


def social_page(data: dict) -> tuple[str, int, int]:
    w, h = 1280, 640
    svg, sh = anatomy_svg(data, 520, compact=True)
    card_h = sh + 36
    tests = count_tests()
    chips = "".join(
        f"<span style='background:rgba(255,255,255,.16);border:1px solid rgba(255,255,255,.35);border-radius:999px;"
        f"padding:8px 18px'>{t}</span>"
        for t in ("No API key", "One Python file", f"{tests} offline tests")
    )
    body = (
        "<div style='position:absolute;inset:0;background:linear-gradient(135deg,#0f766e,#064e3b)'></div>"
        "<div style='position:absolute;left:64px;top:96px;width:560px;color:#fff'>"
        "<div style='display:flex;align-items:center;gap:22px'>"
        "<img src='logo.png' width='96' height='96' style='border-radius:22px'>"
        "<div style='font-size:56px;font-weight:800;line-height:1.04;letter-spacing:-.02em'>Daily Stock<br>Analysis</div></div>"
        "<div style='font-size:34px;font-weight:600;line-height:1.28;margin-top:44px'>Know where a US stock stands "
        "in ten seconds, and exactly why.</div>"
        f"<div style='display:flex;flex-wrap:wrap;gap:12px;margin-top:38px;font-size:19px;font-weight:600'>{chips}</div></div>"
        f"<div style='position:absolute;right:48px;top:{(h - card_h) // 2}px;width:552px;height:{card_h}px;background:#fff;"
        "border-radius:20px;box-shadow:0 24px 60px rgba(0,0,0,.35);overflow:hidden'>"
        "<div style='padding:18px 20px 0;font-size:15px;font-weight:700;color:#475569'>Real scores, split into the factors "
        "behind them</div>"
        f"<div style='position:absolute;left:14px;top:34px'>{svg}</div></div>"
    )
    return page(body, w, h, "#064e3b"), w, h


def main() -> int:
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    data = collect()
    (HERE / "chart-data.json").write_text(json.dumps(data, indent=1) + "\n")
    answer_card(out)
    for name, (doc, w, h) in {
        "anatomy": anatomy_page(data),
        "plan": plan_page(data),
        "social": social_page(data),
    }.items():
        (out / f"{name}.html").write_text(doc)
        (out / f"{name}.size").write_text(f"{w} {h}")
    print(f"wrote pages to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
