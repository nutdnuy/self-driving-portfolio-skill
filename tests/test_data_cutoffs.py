"""Point-in-time data boundary tests."""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "skills" / "macro-regime" / "scripts"))
sys.path.insert(0, str(REPO / "skills" / "asset-class-cma" / "scripts"))
import fetch_macro  # noqa: E402
import fetch_prices as price_module  # noqa: E402


def test_fred_api_requests_the_exact_vintage(monkeypatch):
    captured = {}

    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {"observations": [{"date": "2020-01-01", "value": "1.25"}]}

    def fake_get(url, params, timeout):
        captured.update(params)
        return Response()

    monkeypatch.setattr(fetch_macro.requests, "get", fake_get)
    result = fetch_macro._fetch_api("DFF", "not-a-real-key", "2020-01-15")
    assert result.iloc[0] == 1.25
    assert captured["observation_end"] == "2020-01-15"
    assert captured["realtime_start"] == "2020-01-15"
    assert captured["realtime_end"] == "2020-01-15"


def test_price_cache_is_truncated_at_as_of(tmp_path: Path, monkeypatch):
    cache = tmp_path / "AAA.csv"
    pd.DataFrame(
        {"AAA": [90.0, 101.0, 999.0]},
        index=pd.to_datetime(["2025-05-08", "2026-05-08", "2026-05-09"]),
    ).to_csv(cache)

    def unexpected_download(*args, **kwargs):
        raise AssertionError("cache covering the cutoff should avoid a download")

    monkeypatch.setattr(price_module.yf, "download", unexpected_download)
    prices = price_module.fetch_prices(
        ["AAA"], years=1.0, as_of="2026-05-08", cache_dir=tmp_path
    )
    assert prices.index.max() == pd.Timestamp("2026-05-08")
    assert prices.loc["2026-05-08", "AAA"] == 101.0
    assert 999.0 not in prices["AAA"].values


def test_price_cache_that_is_too_short_is_refetched(tmp_path: Path, monkeypatch):
    cache = tmp_path / "AAA.csv"
    pd.DataFrame(
        {"AAA": [100.0, 101.0]},
        index=pd.to_datetime(["2026-05-07", "2026-05-08"]),
    ).to_csv(cache)
    captured = {}

    def fake_download(ticker, start, end, **kwargs):
        captured.update({"ticker": ticker, "start": start, "end": end})
        return pd.DataFrame(
            {"Close": [90.0, 101.0]},
            index=pd.to_datetime(["2025-05-08", "2026-05-08"]),
        )

    monkeypatch.setattr(price_module.yf, "download", fake_download)
    prices = price_module.fetch_prices(
        ["AAA"], years=1.0, as_of="2026-05-08", cache_dir=tmp_path
    )
    assert captured["ticker"] == "AAA"
    assert captured["start"] == pd.Timestamp("2025-05-08")
    assert prices.index.min() == pd.Timestamp("2025-05-08")
