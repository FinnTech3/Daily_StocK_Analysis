import pytest
import stock_analysis as sa


def test_sma_matches_hand_calculation():
    assert sa.sma([1.0, 2, 3, 4, 5], 3) == 4.0
    assert sa.sma([1.0, 2], 3) is None


def test_rsi_extremes():
    assert sa.rsi([float(i) for i in range(1, 60)]) == 100
    assert sa.rsi([float(i) for i in range(60, 1, -1)]) < 1
    assert sa.rsi([10.0] * 60) == 50
    assert sa.rsi([1.0, 2.0]) is None


def test_rsi_stays_in_range(up, down):
    for bars in (up, down):
        assert 0 <= sa.rsi(bars["close"]) <= 100


def test_macd_histogram_sign_follows_the_trend_turn():
    rising = [100 + i * 0.5 for i in range(80)]
    assert sa.macd_hist(rising + [rising[-1] + 5])[-1] > 0
    assert sa.macd_hist(rising + [rising[-1] - 8])[-1] < 0
    assert sa.macd_hist(rising[:20]) == []


def test_atr_is_positive_and_tracks_range(flat):
    a = sa.atr(flat)
    assert 0 < a < flat["close"][-1] * 0.05


def test_relative_volume_uses_prior_sessions_only():
    assert sa.relative_volume([100.0] * 20 + [300.0]) == 3.0
    assert sa.relative_volume([0.0] * 21) is None


def test_realized_vol_is_zero_for_constant_growth_and_positive_otherwise(up):
    steady = [100 * 1.001**i for i in range(40)]
    assert sa.realized_vol(steady) < 1e-9
    assert 0.05 < sa.realized_vol(up["close"]) < 0.30


def test_realized_vol_matches_the_sample_standard_deviation_of_log_returns(up):
    import math
    import statistics

    closes = up["close"][-21:]
    rets = [math.log(b / a) for a, b in zip(closes, closes[1:], strict=False)]
    assert math.isclose(sa.realized_vol(up["close"]), statistics.stdev(rets) * math.sqrt(252), rel_tol=1e-12)


def test_atr_counts_gaps_up_and_down_from_the_previous_close():
    def bars_of(close):
        return {"high": close, "low": close, "close": close}

    assert sa.atr(bars_of([100.0] * 30 + [110.0])) == pytest.approx(10 / 14)  # an up gap is a true range of 10
    assert sa.atr(bars_of([100.0] * 30 + [90.0])) == pytest.approx(10 / 14)  # so is a down gap
    quiet = {"high": [101.0] * 30, "low": [99.0] * 30, "close": [100.0] * 30}
    assert sa.atr(quiet) == 2.0
    assert sa.atr({"high": [1.0] * 13, "low": [1.0] * 13, "close": [1.0] * 13}) is None


def test_macd_needs_the_signal_line_to_warm_up():
    assert sa.macd_hist([float(i) for i in range(30)]) == []
    assert len(sa.macd_hist([float(i) for i in range(35)])) == 2
