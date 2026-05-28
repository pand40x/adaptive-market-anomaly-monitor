from __future__ import annotations

from market_anomaly.data import fetch_binance_klines


class _FakeResponse:
    def __init__(self, rows: list[list[object]]) -> None:
        self._rows = rows

    def raise_for_status(self) -> None:
        return None

    def json(self) -> list[list[object]]:
        return self._rows


def _row(open_time: int, close_time: int) -> list[object]:
    return [
        open_time,
        "100",
        "105",
        "99",
        "104",
        "1200",
        close_time,
        "0",
        1,
        "0",
        "0",
        "0",
    ]


def test_fetch_binance_klines_paginates_past_single_api_limit(monkeypatch) -> None:
    calls: list[dict[str, object]] = []
    one_hour = 60 * 60 * 1000

    def fake_get(_url: str, *, params: dict[str, object], timeout: int) -> _FakeResponse:
        calls.append(params)
        start = int(params["startTime"])
        if len(calls) == 1:
            return _FakeResponse([_row(start + i * one_hour, start + (i + 1) * one_hour - 1) for i in range(1000)])
        return _FakeResponse([_row(start, start + one_hour - 1)])

    monkeypatch.setattr("market_anomaly.data.requests.get", fake_get)

    frame = fetch_binance_klines("BTCUSDT", interval="1h", years=1, end_time_ms=1_800_000_000_000)

    assert len(frame) == 1001
    assert len(calls) == 2
    assert calls[1]["startTime"] > calls[0]["startTime"]
