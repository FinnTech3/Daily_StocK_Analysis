import io
import json
import urllib.error

import pytest
import stock_analysis as sa
from conftest import END, make_bars, nasdaq_rows


def payload(rows):
    return io.BytesIO(json.dumps({"data": {"tradesTable": {"rows": rows}}}).encode())


def empty():
    return io.BytesIO(json.dumps({"data": None, "status": {"rCode": 400}}).encode())


@pytest.mark.parametrize("raw,clean", [("aapl", "AAPL"), (" brk-b ", "BRK.B"), ("brk/b", "BRK.B"), ("BRK.B", "BRK.B")])
def test_symbol_normalisation(raw, clean):
    assert sa.normalize_symbol(raw) == clean


@pytest.mark.parametrize("bad", ["", "TOOLONG", "AA PL", "../etc", "A;B", "123", "^VIX", "A.B.C"])
def test_bad_symbols_are_rejected(bad):
    with pytest.raises(sa.DataError):
        sa.normalize_symbol(bad)


def test_rows_are_parsed_sorted_and_cleaned():
    rows = nasdaq_rows(make_bars(n=5)) + [
        {"date": "bad", "close": "$1"},
        {"date": "01/02/2020", "close": "N/A"},
        {"date": "01/03/2020", "close": "$5.00", "high": "N/A", "low": "--", "volume": "--"},
    ]
    bars = sa.parse_rows(rows)
    assert bars["date"] == sorted(bars["date"]) and len(bars["close"]) == 6
    assert bars["high"][0] == bars["low"][0] == 5.0 and bars["volume"][0] == 0.0


def test_fetch_uses_the_etf_class_when_stocks_has_no_rows():
    seen = []

    def opener(req, timeout):
        seen.append(req.full_url)
        return empty() if "assetclass=stocks" in req.full_url else payload(nasdaq_rows(make_bars(n=70)))

    bars = sa.fetch_history("spy", opener=opener, today=END)
    assert len(bars["close"]) == 70 and "assetclass=etf" in seen[-1] and "/SPY/" in seen[0]


def test_unknown_ticker_fails_fast_without_retrying():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        return empty()

    with pytest.raises(sa.DataError, match="no price data"):
        sa.fetch_history("ZZZZ", opener=opener, sleep=lambda s: None)
    assert len(calls) == 2  # stocks, then etf, once each


def test_network_errors_retry_then_report_the_cause():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        raise urllib.error.URLError("connection refused")

    with pytest.raises(sa.DataError, match="after 3 tries: connection refused"):
        sa.fetch_history("AAPL", opener=opener, sleep=lambda s: None)
    assert len(calls) == 3


def test_one_bad_symbol_does_not_sink_the_batch():
    def fetch(sym):
        if sym == "BOOM":
            raise ValueError("odd")
        return make_bars()

    out = sa.fetch_many(["AAPL", "BOOM"], fetch)
    assert isinstance(out["BOOM"], sa.DataError) and "close" in out["AAPL"]


@pytest.fixture
def fetch():
    frames = {"SPY": make_bars("flat"), "GOOD": make_bars("up"), "TWO": make_bars("up", seed=3)}

    def _fetch(sym):
        if sym not in frames:
            raise sa.DataError(f"no price data for {sym}; check the ticker")
        return frames[sym]

    return _fetch


def test_all_good_exits_zero(fetch, capsys):
    assert sa.main(["analyze", "GOOD"], fetch) == 0
    assert "Not financial advice" in capsys.readouterr().out


def test_partial_failure_exits_one_and_still_reports(fetch, capsys):
    assert sa.main(["analyze", "GOOD", "NOPE", "bad!"], fetch) == 1
    out = capsys.readouterr().out
    assert "## GOOD" in out and "Could not analyze" in out and "bad!" in out


def test_total_failure_exits_two(fetch):
    assert sa.main(["analyze", "NOPE"], fetch) == 2


def test_json_output_is_valid(fetch, capsys):
    sa.main(["analyze", "GOOD", "--json", "--account", "10000"], fetch)
    doc = json.loads(capsys.readouterr().out)
    assert doc["analyses"][0]["symbol"] == "GOOD" and doc["analyses"][0]["plan"]["shares"]
    assert set(doc) == {"regime", "analyses", "errors", "disclaimer"}


@pytest.mark.parametrize(
    "flags", [["--account", "-5"], ["--account", "nan"], ["--risk", "0"], ["--risk", "50"], ["--risk", "inf"]]
)
def test_bad_numbers_are_rejected(fetch, flags):
    assert sa.main(["analyze", "GOOD", *flags], fetch) == 2


def test_duplicates_are_analysed_once_and_table_columns_line_up(fetch, capsys):
    sa.main(["analyze", "good", "GOOD", "TWO"], fetch)
    out = capsys.readouterr().out
    assert out.count("## GOOD") == 1
    rows = [ln for ln in out.splitlines() if ln.startswith(("| Symbol", "| GOOD", "| TWO"))]
    assert len(rows) == 3 and len({ln.count("|") for ln in rows}) == 1


def test_sections_follow_the_table_order_highest_score_first(capsys):
    frames = {"SPY": make_bars("flat"), "DOWN": make_bars("down"), "UP": make_bars("up")}
    assert sa.main(["analyze", "DOWN", "UP"], frames.__getitem__) == 0
    out = capsys.readouterr().out
    table = [ln.split("|")[1].strip() for ln in out.splitlines() if ln.startswith(("| UP", "| DOWN"))]
    assert table == ["UP", "DOWN"]
    assert out.index("## UP") < out.index("## DOWN")


def test_unknown_ticker_message_is_a_whole_sentence_and_says_what_to_check():
    with pytest.raises(sa.DataError) as err:
        sa.fetch_history("NOPE", opener=lambda *a, **k: io.BytesIO(b'{"data": {"tradesTable": {"rows": []}}}'))
    assert str(err.value).endswith("endpoint may have changed.")


def test_market_command(fetch, capsys):
    assert sa.main(["market"], fetch) == 0
    assert "Market regime" in capsys.readouterr().out
    assert sa.main(["market", "--json"], lambda s: (_ for _ in ()).throw(sa.DataError("down"))) == 1


def test_no_command_prints_help(capsys):
    assert sa.main([]) == 2
    assert "usage" in capsys.readouterr().out.lower()
