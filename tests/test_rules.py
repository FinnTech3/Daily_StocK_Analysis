"""Pin every weight and threshold in the score, so a changed constant fails a test."""

from datetime import date, timedelta

import pytest
import stock_analysis as sa
from conftest import make_bars

TODAY = date(2026, 11, 12)


def bars_from(close, volume=None, today=date(2026, 11, 11)):
    """Bars with a zero daily range, so ATR is controlled by the closes alone."""
    n = len(close)
    days = [today - timedelta(days=n - 1 - i) for i in range(n)]
    return {"date": days, "high": list(close), "low": list(close), "close": list(close), "volume": volume or [1e6] * n}


def factor(analysis, name):
    return next((f for f in analysis["factors"] if f["name"] == name), None)


def run(close, **kw):
    kw.setdefault("today", TODAY)
    return sa.analyze("T", bars_from(close), **kw)


# --- trend


def test_trend_is_worth_plus_and_minus_forty_when_everything_lines_up():
    assert factor(run([100 * 1.01**i for i in range(300)]), "Trend")["points"] == 40
    assert factor(run([100 * 0.99**i for i in range(300)]), "Trend")["points"] == -40


def test_trend_without_a_200_day_average_tops_out_at_twenty_three():
    assert factor(run([100 * 1.01**i for i in range(120)]), "Trend")["points"] == 23


def test_price_equal_to_an_average_scores_zero_for_it():
    why = factor(run([100.0] * 300), "Trend")
    assert why["points"] == 0 and why["why"].count("at ") == 3


# --- momentum


@pytest.mark.parametrize(
    "rsi,adjust,zone",
    [
        (100, -5, "stretched"),
        (70, -5, "stretched"),
        (69.9, 10, "healthy"),
        (55, 10, "healthy"),
        (54.9, 0, "neutral"),
        (45, 0, "neutral"),
        (44.9, -10, "weak"),
        (30, -10, "weak"),
        (29.9, -5, "oversold"),
        (0, -5, "oversold"),
    ],
)
def test_rsi_zones(monkeypatch, rsi, adjust, zone):
    monkeypatch.setattr(sa, "rsi", lambda closes: rsi)
    monkeypatch.setattr(sa, "macd_hist", lambda closes: [0.0, 0.0, 0.0, 0.0, 0.0])
    m = factor(run([100.0] * 300), "Momentum")
    assert m["points"] == adjust and f"({zone})" in m["why"]


@pytest.mark.parametrize(
    "before,now,points,words",
    [(-1.0, 2.0, 15, "positive and rising"), (3.0, 2.0, 5, "positive and falling"),
     (1.0, -2.0, -15, "negative and falling"), (-3.0, -2.0, -5, "negative and rising"),
     (2.0, 2.0, 10, "positive and flat"), (0.0, 0.0, 0, "zero and flat")],
)  # fmt: skip
def test_macd_points_and_wording(monkeypatch, before, now, points, words):
    monkeypatch.setattr(sa, "rsi", lambda closes: 50.0)  # the neutral zone adds nothing
    monkeypatch.setattr(sa, "macd_hist", lambda closes: [9.0, before, 9.0, 9.0, now])  # [-4] is before, [-1] is now
    m = factor(run([100.0] * 300), "Momentum")
    assert m["points"] == points and words in m["why"]


# --- volume


def volume_case(last, up=True):
    close = [100.0] * 300
    close[-1] = 101.0 if up else 99.0
    return sa.analyze("T", bars_from(close, [100.0] * 299 + [last]), today=TODAY)


def test_volume_needs_one_point_two_times_the_average():
    assert factor(volume_case(120.0), "Volume")["points"] == 10
    assert factor(volume_case(119.9), "Volume")["points"] == 0
    assert factor(volume_case(120.0, up=False), "Volume")["points"] == -10
    assert "1.2x average volume on an up day" in factor(volume_case(120.0), "Volume")["why"]


def test_an_unchanged_close_counts_as_an_up_day():
    close = [100.0] * 300
    a = sa.analyze("T", bars_from(close, [100.0] * 299 + [500.0]), today=TODAY)
    assert factor(a, "Volume")["points"] == 10


# --- relative strength


def rs_points(change, spy_change=0.0):
    close = [50.0] * 236 + [100.0] + [102.0] * 62 + [100 * (1 + change)]
    spy = bars_from([100.0] * 299 + [100 * (1 + spy_change)])
    return factor(run(close, spy=spy), "Relative strength")


def test_relative_strength_uses_the_63_session_window_and_clamps():
    # close[-64] is 100, the 62 sessions after it are 102: a 63-session window sees +5%, a 60-session one sees +2.9%
    r = rs_points(0.05)
    assert "+5.0% vs S&P 500 +0.0% over 63 sessions" in r["why"] and r["points"] == 7.5
    assert rs_points(0.10)["points"] == 15 and rs_points(0.50)["points"] == 15
    assert rs_points(-0.10)["points"] == -15 and rs_points(-0.50)["points"] == -15
    assert rs_points(0.10, spy_change=0.10)["points"] == 0


def test_relative_strength_is_skipped_without_market_data_or_history():
    assert factor(run([100.0] * 300), "Relative strength") is None
    flat_spy = bars_from([100.0] * 63)
    assert factor(run([100.0] * 300, spy=flat_spy), "Relative strength") is None
    assert factor(run([100.0] * 63, spy=bars_from([100.0] * 300)), "Relative strength") is None
    assert factor(run([100.0] * 64, spy=bars_from([100.0] * 64)), "Relative strength") is not None


# --- extension and regime factors


@pytest.mark.parametrize("atr,fires", [(3.0, True), (3.16, True), (3.17, False), (4.0, False)])
def test_extension_fires_above_three_atr(monkeypatch, atr, fires):
    monkeypatch.setattr(sa, "atr", lambda bars: atr)
    close = [100.0] * 299 + [110.0]  # 20-day average 100.5, so three ATR is 3.165 at most
    a = run(close)
    assert (factor(a, "Extension") is not None) == fires
    if fires:
        assert factor(a, "Extension")["points"] == -8
        assert a["plan"] is None or a["plan"]["entry"] == pytest.approx(100.5)


def test_regime_points_are_added_once_and_only_when_nonzero(up):
    base = sa.analyze("T", up, today=TODAY)
    assert factor(base, "Market regime") is None
    on = sa.analyze("T", up, regime={"label": "risk-on", "points": 5}, today=TODAY)
    assert factor(on, "Market regime") == {"name": "Market regime", "points": 5, "why": "risk-on market"}
    assert on["score"] == base["score"] + 5


def test_the_score_is_clamped_to_plus_and_minus_one_hundred(up):
    low = sa.analyze("T", up, regime={"label": "risk-off", "points": -300}, today=TODAY)
    high = sa.analyze("T", up, regime={"label": "risk-on", "points": 300}, today=TODAY)
    assert (low["score"], low["bias"]) == (-100, "Bearish") and (high["score"], high["bias"]) == (100, "Bullish")


# --- regime


def vol_patch(monkeypatch, value):
    monkeypatch.setattr(sa, "realized_vol", lambda closes: value)


@pytest.mark.parametrize("vol,label", [(0.159, "risk-on"), (0.16, "neutral"), (0.279, "neutral"), (0.28, "risk-off")])
def test_regime_volatility_thresholds(monkeypatch, vol, label):
    vol_patch(monkeypatch, vol)
    assert sa.classify_regime(bars_from([100 * 1.002**i for i in range(300)]))["label"] == label


def test_regime_points():
    assert sa.REGIME_POINTS == {"risk-on": 5, "neutral": 0, "risk-off": -15, "unknown": 0}


def test_price_at_its_200_day_average_is_not_risk_off():
    assert sa.classify_regime(bars_from([100.0] * 300))["label"] == "neutral"


def test_risk_on_needs_price_above_the_50_day_above_the_200_day(monkeypatch):
    vol_patch(monkeypatch, 0.05)
    close = [100 + 0.5 * i for i in range(250)] + [224.5 - 0.4 * i for i in range(1, 51)]
    assert close[-1] > sa.sma(close, 200) and close[-1] < sa.sma(close, 50)
    assert sa.classify_regime(bars_from(close))["label"] == "neutral"


def test_regime_needs_200_sessions():
    assert sa.classify_regime(bars_from([100.0] * 199))["label"] == "unknown"
    assert sa.classify_regime(bars_from([100.0] * 200))["label"] != "unknown"


# --- plan


def test_plan_levels_are_two_atr_stop_and_one_and_a_half_and_three_r():
    plan, reason = sa.make_plan(100.0, 98.0, 2.0, "Bullish", False, 10_000, 1.0)
    assert reason is None
    assert (plan["entry"], plan["stop"], plan["target_1"], plan["target_2"]) == (100.0, 96.0, 106.0, 112.0)
    assert plan["risk_per_share"] == 4.0 and plan["shares"] == 25 and plan["position_value"] == 2500.0


def test_shares_are_capped_by_what_the_account_can_buy():
    plan, _ = sa.make_plan(100.0, 98.0, 2.0, "Bullish", False, 1000, 10.0)
    assert plan["shares"] == 10 and plan["position_value"] == 1000.0


def test_shares_round_down_and_a_lean_bullish_bias_also_gets_a_plan():
    plan, _ = sa.make_plan(100.0, 98.0, 2.0, "Lean bullish", False, 1999, 1.0)
    assert plan["shares"] == 4  # 19.99 / 4 rounded down


def test_no_account_means_no_share_count():
    plan, _ = sa.make_plan(100.0, 98.0, 2.0, "Bullish", False, None, 1.0)
    assert plan["shares"] is None and plan["position_value"] is None


def test_a_stop_below_zero_is_refused():
    plan, reason = sa.make_plan(3.0, 3.0, 2.0, "Bullish", False, None, 1.0)
    assert plan is None and "stop" in reason


# --- warnings and limits


@pytest.mark.parametrize("today,warns", [(date(2026, 11, 16), False), (date(2026, 11, 17), True)])
def test_stale_data_warns_after_five_days(today, warns):
    a = sa.analyze("T", make_bars("up"), today=today)  # the last bar is 11 Nov
    assert any("latest bar is 6 days old" in w for w in a["warnings"]) == warns
    assert not any("latest bar is 5 days old" in w for w in a["warnings"])


def test_history_limits():
    assert sa.analyze("T", make_bars(n=60), today=TODAY)["score"] is not None
    with pytest.raises(sa.DataError, match="only 59 sessions"):
        sa.analyze("T", make_bars(n=59), today=TODAY)
    short = sa.analyze("T", make_bars(n=239), today=TODAY)["warnings"]
    assert any("52-week" in w for w in short)
    assert not any("52-week" in w for w in sa.analyze("T", make_bars(n=240), today=TODAY)["warnings"])
    assert not any("200-day" in w for w in sa.analyze("T", make_bars(n=240), today=TODAY)["warnings"])


def test_levels_use_the_20_day_and_52_week_windows():
    bars = make_bars("flat", n=300)
    n = len(bars["low"])
    bars["low"][n - 20], bars["low"][n - 21] = 1.0, 0.5
    bars["high"][n - 20], bars["high"][n - 21] = 900.0, 950.0
    bars["low"][n - 252], bars["low"][n - 253] = 2.0, 0.25
    bars["high"][n - 252], bars["high"][n - 253] = 990.0, 999.0
    lv = sa.analyze("T", bars, today=TODAY)["levels"]
    assert (lv["support_20d"], lv["resistance_20d"]) == (1.0, 900.0)
    assert (lv["low_52w"], lv["high_52w"]) == (0.5, 990.0)  # 0.5 and 900 sit inside the window, 0.25 does not


@pytest.mark.parametrize(
    "score,label",
    [(100, "Bullish"), (55, "Bullish"), (54, "Lean bullish"), (20, "Lean bullish"), (19, "Neutral"), (0, "Neutral"),
     (-19, "Neutral"), (-20, "Lean bearish"), (-54, "Lean bearish"), (-55, "Bearish"), (-100, "Bearish")],
)  # fmt: skip
def test_every_bias_boundary(score, label):
    assert sa.bias_label(score) == label


def test_position_value_is_rounded_to_cents():
    plan, _ = sa.make_plan(33.333333, 30.0, 1.0, "Bullish", False, 1000, 1.0)
    assert plan["shares"] == 5 and plan["position_value"] == 166.67


def test_a_neutral_bias_says_neutral_and_a_bearish_one_says_bearish():
    assert "neutral" in sa.make_plan(100.0, 98.0, 2.0, "Neutral", False, None, 1.0)[1]
    assert "bearish" in sa.make_plan(100.0, 98.0, 2.0, "Bearish", False, None, 1.0)[1]
