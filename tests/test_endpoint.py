"""The Nasdaq endpoint is undocumented, so every way it can go wrong must end in a plain message."""

import io
import json
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import stock_analysis as sa
from conftest import END, make_bars, nasdaq_rows


def reply(body):
    data = body if isinstance(body, bytes) else json.dumps(body).encode()
    return lambda req, timeout: io.BytesIO(data)


def fetch_with(body, **kw):
    return sa.fetch_history("AAPL", opener=reply(body), sleep=lambda s: None, **kw)


GOOD_ROW = {"date": "11/10/2026", "close": "$10", "high": "$11", "low": "$9", "volume": "5"}


@pytest.mark.parametrize("body", [[], "oops", None, 7, {"data": "oops"}])
def test_a_reply_of_the_wrong_shape_says_the_endpoint_may_have_changed(body):
    with pytest.raises(sa.DataError, match="unexpected reply for AAPL.*undocumented"):
        fetch_with(body)


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"data": {}},
        {"data": {"tradesTable": []}},
        {"data": {"table": {"rows": [GOOD_ROW]}}},
        {"data": {"tradesTable": {"rows": ["x", 1, None]}}},
    ],
)
def test_a_reply_with_no_usable_rows_points_at_the_ticker_and_the_endpoint(body):
    with pytest.raises(sa.DataError, match="no price data for AAPL; check the ticker.*may have changed"):
        fetch_with(body)


def test_a_non_json_reply_is_retried_then_reported_in_plain_words():
    calls = []

    def opener(req, timeout):
        calls.append(1)
        return io.BytesIO(b"<html>Access Denied</html>")

    with pytest.raises(sa.DataError) as err:
        sa.fetch_history("AAPL", opener=opener, sleep=lambda s: None)
    assert len(calls) == 3
    assert "reply was not JSON" in str(err.value) and "undocumented" in str(err.value)
    assert "Expecting value" not in str(err.value)


def test_a_reply_that_is_not_utf8_is_not_a_traceback():
    with pytest.raises(sa.DataError, match="not JSON"):
        fetch_with(b"\xff\xfe\x00junk")


def test_replies_are_read_with_a_size_cap():
    asked = []

    class Resp(io.BytesIO):
        def read(self, n=-1):
            asked.append(n)
            return super().read(n)

    with pytest.raises(sa.DataError):
        sa.fetch_history("AAPL", opener=lambda req, timeout: Resp(b'{"data": null}'), sleep=lambda s: None)
    assert asked and all(0 < n <= 5_000_000 for n in asked)


def test_an_oversized_reply_is_cut_off_and_reported():
    big = b'{"data": {"tradesTable": {"rows": [' + b'{"date": "11/10/2026", "close": "1"},' * 400_000 + b"]}}}"
    assert len(big) > 5_000_000
    with pytest.raises(sa.DataError, match="not JSON"):
        fetch_with(big)


def test_market_survives_a_changed_endpoint_and_says_why(capsys):
    assert sa.main(["market"], lambda s: fetch_with([])) == 1
    out = capsys.readouterr().out
    assert "Market regime: Unknown" in out and "unexpected reply" in out and "undocumented" in out


def test_analyze_with_a_changed_endpoint_exits_two_with_the_reason_in_json(capsys):
    def fetch(sym):
        return fetch_with("not json")

    assert sa.main(["analyze", "AAPL", "--json"], fetch) == 2
    doc = json.loads(capsys.readouterr().out)
    assert doc["analyses"] == [] and "undocumented" in doc["errors"]["AAPL"]
    assert doc["regime"]["label"] == "unknown" and "undocumented" in doc["regime"]["reasons"][0]


def test_the_cause_of_a_failed_market_read_is_kept_in_the_answer(capsys):
    def fetch(sym):
        if sym == "SPY":
            raise sa.DataError("could not fetch SPY after 3 tries: Too Many Requests")
        return make_bars("up")

    assert sa.main(["analyze", "GOOD", "--json"], fetch) == 0
    doc = json.loads(capsys.readouterr().out)
    assert "Too Many Requests" in doc["regime"]["reasons"][0]
    assert not any(f["name"] in ("Relative strength", "Market regime") for f in doc["analyses"][0]["factors"])


# --- the request itself


def test_the_request_asks_for_the_right_window_and_times_out():
    seen = []

    def opener(req, timeout):
        seen.append((req.full_url, timeout))
        return io.BytesIO(json.dumps({"data": None}).encode())

    with pytest.raises(sa.DataError):
        sa.fetch_history("brk-b", opener=opener, today=END)
    (url, timeout), (url2, _) = seen
    query = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    assert urllib.parse.urlparse(url).path.endswith("/BRK.B/historical") and 0 < timeout <= 30
    assert query == {"assetclass": ["stocks"], "fromdate": ["2025-09-17"], "todate": ["2026-11-11"], "limit": ["500"]}
    assert urllib.parse.parse_qs(urllib.parse.urlparse(url2).query)["assetclass"] == ["etf"]


def test_backoff_doubles_between_tries_and_stops_after_the_last():
    sleeps = []

    def opener(req, timeout):
        raise TimeoutError()

    with pytest.raises(sa.DataError, match="after 3 tries: TimeoutError"):
        sa.fetch_history("AAPL", opener=opener, sleep=sleeps.append, backoff=1.5)
    assert sleeps == [1.5, 3.0]


def test_a_symbol_is_fetched_once_however_often_it_is_listed():
    seen = []

    def fetch(sym):
        seen.append(sym)
        return make_bars("up")

    sa.main(["analyze", "good", "GOOD", "Good", "SPY"], fetch)
    assert sorted(seen) == ["GOOD", "SPY", "SPY"]  # SPY once for the market read, once because it was asked for


# --- hostile row data


@pytest.mark.parametrize("bad", ["nan", "NaN", "inf", "-inf", "Infinity", "1e30", "0", "-5", "$0.00", "", None, "abc"])
def test_unusable_closes_are_dropped(bad):
    rows = nasdaq_rows(make_bars(n=3)) + [{**GOOD_ROW, "date": "01/05/2020", "close": bad}]
    assert len(sa.parse_rows(rows)["close"]) == 3


@pytest.mark.parametrize("field", ["high", "low", "volume"])
@pytest.mark.parametrize("bad", ["nan", "inf", "1e30"])
def test_unusable_highs_lows_and_volumes_fall_back(field, bad):
    bars = sa.parse_rows([{**GOOD_ROW, field: bad}])
    fallback = {"high": ("high", 10.0), "low": ("low", 10.0), "volume": ("volume", 0.0)}[field]
    assert bars[fallback[0]] == [fallback[1]]  # the close stands in for a missing high or low; volume becomes 0
    assert bars["close"] == [10.0]


def test_duplicate_dates_keep_one_bar_and_the_later_row_wins():
    rows = [{**GOOD_ROW, "close": "$10"}, {**GOOD_ROW, "close": "$12", "high": "$13"}]
    bars = sa.parse_rows(rows)
    assert bars["close"] == [12.0] and len(bars["date"]) == 1


def test_rows_come_back_oldest_first():
    rows = [
        {**GOOD_ROW, "date": "11/10/2026", "close": "$3"},
        {**GOOD_ROW, "date": "11/08/2026", "close": "$1"},
        {**GOOD_ROW, "date": "11/09/2026", "close": "$2"},
    ]
    assert sa.parse_rows(rows)["close"] == [1.0, 2.0, 3.0]


def test_a_batch_with_one_nan_row_still_scores_every_ticker(capsys):
    rows = nasdaq_rows(make_bars("up"))
    rows[5]["close"] = "nan"
    rows[6]["close"] = "inf"
    bars = sa.parse_rows(rows)
    a = sa.analyze("T", bars)
    assert isinstance(a["score"], int) and a["close"] > 0


# --- real HTTP against a local server, with the address swapped in


@pytest.fixture
def server(monkeypatch):
    state = {"status": 200, "body": b"{}", "hits": 0}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            state["hits"] += 1
            self.send_response(state["status"])
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(state["body"])))
            self.end_headers()
            self.wfile.write(state["body"])

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, args=(0.01,), daemon=True).start()
    monkeypatch.setattr(sa, "API", f"http://127.0.0.1:{httpd.server_port}/{{symbol}}/historical")
    yield state
    httpd.shutdown()
    httpd.server_close()


def test_real_http_success(server):
    server["body"] = json.dumps({"data": {"tradesTable": {"rows": nasdaq_rows(make_bars("up"))}}}).encode()
    assert len(sa.fetch_history("AAPL", sleep=lambda s: None)["close"]) == 300
    assert server["hits"] == 1


@pytest.mark.parametrize(
    "status,phrase", [(403, "Forbidden"), (429, "Too Many Requests"), (500, "Internal Server Error")]
)
def test_http_errors_are_named_and_retried(server, status, phrase):
    server["status"] = status
    with pytest.raises(sa.DataError, match=f"after 3 tries: {phrase}.*undocumented"):
        sa.fetch_history("AAPL", sleep=lambda s: None)
    assert server["hits"] == 3


def test_real_http_html_page_is_reported_as_not_json(server):
    server["body"] = b"<html><body>Please enable JavaScript</body></html>"
    with pytest.raises(sa.DataError, match="reply was not JSON"):
        sa.fetch_history("AAPL", sleep=lambda s: None)


def test_connection_refused_is_a_message_not_a_traceback(monkeypatch):
    monkeypatch.setattr(sa, "API", "http://127.0.0.1:9/{symbol}/historical")
    with pytest.raises(sa.DataError, match="after 2 tries"):
        sa.fetch_history("AAPL", retries=2, sleep=lambda s: None)


# --- command line input


def test_commas_and_spaces_inside_one_argument_are_split(capsys):
    seen = []

    def fetch(sym):
        seen.append(sym)
        return make_bars("up")

    assert sa.main(["analyze", "aapl, msft", "nvda,tsla;", "brk-b"], fetch) == 1  # "tsla;" is not a ticker
    out = capsys.readouterr().out
    assert sorted(set(seen) - {"SPY"}) == ["AAPL", "BRK.B", "MSFT", "NVDA"] and "tsla;" in out


@pytest.mark.parametrize("arg", ["", " ", ",", " , "])
def test_blank_ticker_arguments_are_an_error_not_a_silent_exit(arg, capsys):
    assert sa.main(["analyze", arg], lambda s: make_bars("up")) == 2
    assert "not a valid US ticker" in capsys.readouterr().out


def test_risk_of_exactly_ten_percent_is_allowed_and_a_hair_more_is_not():
    assert sa.main(["analyze", "GOOD", "--risk", "10"], lambda s: make_bars("up")) == 0
    assert sa.main(["analyze", "GOOD", "--risk", "10.01"], lambda s: make_bars("up")) == 2
    assert sa.main(["analyze", "GOOD", "--account", "0"], lambda s: make_bars("up")) == 2


def test_the_table_is_sorted_best_first_and_the_disclaimer_is_the_last_line(capsys):
    frames = {"SPY": make_bars("flat"), "UP": make_bars("up"), "DN": make_bars("down")}
    sa.main(["analyze", "DN", "UP"], lambda s: frames[s])
    out = capsys.readouterr().out
    rows = [ln.split("|")[1].strip() for ln in out.splitlines() if ln.startswith(("| UP", "| DN"))]
    assert rows == ["UP", "DN"]
    assert out.rstrip().splitlines()[-1] == f"*{sa.DISCLAIMER}*"


@pytest.mark.parametrize("rows", [5, {"a": 1}, "abc", [[1, 2]]])
def test_rows_of_the_wrong_type_never_raise_a_traceback(rows):
    with pytest.raises(sa.DataError, match="AAPL"):
        fetch_with({"data": {"tradesTable": {"rows": rows}}})


def test_the_request_looks_like_a_browser_asking_for_json():
    seen = []

    def opener(req, timeout):
        seen.append(dict(req.header_items()))
        return io.BytesIO(b'{"data": null}')

    with pytest.raises(sa.DataError):
        sa.fetch_history("AAPL", opener=opener)
    assert seen[0]["User-agent"].startswith("Mozilla/5.0") and "application/json" in seen[0]["Accept"]


@pytest.mark.parametrize("arg", ["AAPL MSFT", "AAPL\tMSFT", "AAPL\nMSFT", "AAPL ,  MSFT"])
def test_a_quoted_list_in_one_argument_is_split(arg, capsys):
    seen = []

    def fetch(sym):
        seen.append(sym)
        return make_bars("up")

    assert sa.main(["analyze", arg], fetch) == 0
    assert sorted(set(seen) - {"SPY"}) == ["AAPL", "MSFT"]


@pytest.mark.parametrize("ok", ["A", "ABCDE", "BRK.B", "ABC.DE", "a.b"])
def test_ticker_shapes_that_are_accepted(ok):
    assert sa.normalize_symbol(ok) == ok.upper()


@pytest.mark.parametrize("bad", ["ABCDEF", "A.BCD", ".B", "A.", "AB-1", "A B"])
def test_ticker_shapes_that_are_rejected(bad):
    with pytest.raises(sa.DataError):
        sa.normalize_symbol(bad)


def test_a_high_below_the_close_or_a_low_above_it_is_pulled_to_the_close():
    bars = sa.parse_rows([{**GOOD_ROW, "close": "$10", "high": "$8", "low": "$12"}])
    assert bars["high"] == [10.0] and bars["low"] == [10.0]


def test_market_json_carries_the_disclaimer(capsys):
    assert sa.main(["market", "--json"], lambda s: make_bars("up")) == 0
    doc = json.loads(capsys.readouterr().out)
    assert doc["disclaimer"] == sa.DISCLAIMER and doc["regime"]["spy_close"] == round(make_bars("up")["close"][-1], 2)


def test_one_ticker_gets_no_summary_table_but_several_do(capsys):
    sa.main(["analyze", "GOOD"], lambda s: make_bars("up"))
    assert "| Symbol |" not in capsys.readouterr().out
    sa.main(["analyze", "GOOD", "TWO"], lambda s: make_bars("up"))
    assert "| Symbol |" in capsys.readouterr().out


def test_the_written_report_shows_levels_plan_and_share_count(capsys):
    sa.main(["analyze", "GOOD", "--account", "50000"], lambda s: make_bars("up"))
    out = capsys.readouterr().out
    assert "50-day $" in out and "200-day $" in out and "52-week range $" in out
    assert "**Reference plan (long)**: entry $" in out and "Sized for your risk: **" in out and " shares**" in out
    capsys.readouterr()
    sa.main(["analyze", "GOOD"], lambda s: make_bars("up"))
    out = capsys.readouterr().out
    assert "Reference plan" in out and "Sized for your risk" not in out
    capsys.readouterr()
    sa.main(["analyze", "BAD"], lambda s: make_bars("down"))
    assert "**No long setup**: the bias is bearish" in capsys.readouterr().out
