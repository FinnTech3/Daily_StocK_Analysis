import json
from datetime import date

import pytest
import stock_analysis as sa
from conftest import make_bars

TODAY = date(2026, 11, 12)


def test_uptrend_scores_bullish_with_a_plan(up):
    a = sa.analyze("UP", up, spy=make_bars("flat"), today=TODAY)
    assert a["score"] > 20 and a["bias"] in ("Bullish", "Lean bullish")
    p = a["plan"]
    assert p and p["stop"] < p["entry"] < p["target_1"] < p["target_2"]


def test_downtrend_scores_bearish_and_has_no_plan(down):
    a = sa.analyze("DN", down, spy=make_bars("flat"), today=TODAY)
    assert a["score"] < -20 and a["plan"] is None
    assert "bearish" in a["no_plan_reason"]


def test_perfectly_flat_price_is_neutral_not_bearish():
    bars = make_bars("flat")
    for key in ("high", "low", "close"):
        bars[key] = [50.0] * len(bars["close"])
    a = sa.analyze("FLAT", bars, today=TODAY)
    assert a["bias"] == "Neutral" and a["plan"] is None


def test_score_is_the_sum_of_its_factors(up):
    a = sa.analyze("UP", up, today=TODAY)
    assert -100 <= a["score"] <= 100
    assert round(sum(f["points"] for f in a["factors"])) == a["score"]


def test_risk_off_regime_lowers_the_score(up):
    calm = sa.analyze("UP", up, regime={"label": "neutral", "points": 0}, today=TODAY)
    scared = sa.analyze("UP", up, regime={"label": "risk-off", "points": -15}, today=TODAY)
    assert scared["score"] == calm["score"] - 15


def test_position_size_respects_risk_budget(up):
    p = sa.analyze("UP", up, account=50_000, risk_pct=1.0, today=TODAY)["plan"]
    assert p["shares"] and p["shares"] * p["risk_per_share"] <= 500
    assert p["position_value"] <= 50_000


def test_tiny_account_is_told_so(up):
    p = sa.analyze("UP", up, account=10, today=TODAY)["plan"]
    assert p["shares"] == 0 and "too small" in p["note"]


@pytest.mark.parametrize("bias", ["Neutral", "Lean bearish", "Bearish"])
def test_only_a_bullish_bias_gets_a_plan(bias):
    plan, reason = sa.make_plan(100.0, 98.0, 2.0, bias, False, None, 1.0)
    assert plan is None and reason


def test_extended_price_waits_for_a_pullback():
    plan, _ = sa.make_plan(120.0, 100.0, 2.0, "Bullish", True, None, 1.0)
    assert plan["entry"] == 100.0 and "pullback" in plan["note"]


def test_short_history_is_rejected():
    with pytest.raises(sa.DataError):
        sa.analyze("X", make_bars(n=30), today=TODAY)


def test_limited_history_warns_but_works():
    a = sa.analyze("X", make_bars(n=120), today=TODAY)
    assert any("200-day" in w for w in a["warnings"]) and any("52-week" in w for w in a["warnings"])


def test_stale_data_is_flagged(up):
    a = sa.analyze("UP", up, today=date(2026, 12, 25))
    assert any("days old" in w for w in a["warnings"])


def test_a_split_sized_jump_is_flagged(up):
    up["close"][-30:] = [c / 2 for c in up["close"][-30:]]
    a = sa.analyze("UP", up, today=TODAY)
    assert any("possible split" in w for w in a["warnings"])


@pytest.mark.parametrize(
    "score,label",
    [(80, "Bullish"), (55, "Bullish"), (20, "Lean bullish"), (0, "Neutral"), (-20, "Lean bearish"), (-55, "Bearish")],
)
def test_bias_thresholds(score, label):
    assert sa.bias_label(score) == label


def test_analysis_is_json_serialisable(up):
    json.dumps(sa.analyze("UP", up, today=TODAY))


def test_regime_rules():
    assert sa.classify_regime(make_bars("up"))["label"] in ("risk-on", "neutral")
    assert sa.classify_regime(make_bars("down"))["label"] == "risk-off"
    assert sa.classify_regime(make_bars(n=50))["label"] == "unknown"
    assert sa.classify_regime(None)["points"] == 0
    wild = make_bars("up")
    wild["close"][-21:] = [wild["close"][-22] * (1.06 if i % 2 else 0.95) for i in range(21)]
    assert sa.classify_regime(wild)["label"] == "risk-off"
