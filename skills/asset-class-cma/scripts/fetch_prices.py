"""Fetch adjusted-close history with an explicit point-in-time cutoff."""
from __future__ import annotations

import re
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

_CACHE = Path(__file__).resolve().parents[3] / ".cache" / "prices"
_TICKER_RE = re.compile(r"^[A-Z0-9][A-Z0-9.^=_-]{0,19}$")


def _normalise_as_of(as_of: date | str | None) -> pd.Timestamp:
    cutoff = pd.Timestamp(as_of or date.today()).normalize()
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    if cutoff.date() > date.today():
        raise ValueError(f"as_of cannot be in the future: {cutoff.date()}")
    return cutoff


def fetch_prices(
    tickers: list[str],
    years: float = 10.0,
    as_of: date | str | None = None,
    cache_dir: str | Path | None = None,
) -> pd.DataFrame:
    """Return adjusted closes without observations after ``as_of``.

    Fail closed when any requested ticker is unavailable. Never silently shrink
    the IPS asset universe.
    """
    if years <= 0:
        raise ValueError("years must be positive")
    requested = [ticker.strip().upper() for ticker in tickers]
    if not requested or len(requested) != len(set(requested)):
        raise ValueError("tickers must be a non-empty unique list")
    invalid = [ticker for ticker in requested if not _TICKER_RE.fullmatch(ticker)]
    if invalid:
        raise ValueError(f"Unsupported ticker syntax: {invalid}")

    cache_root = Path(cache_dir) if cache_dir is not None else _CACHE
    cache_root.mkdir(parents=True, exist_ok=True)
    end = _normalise_as_of(as_of)
    start = end - pd.DateOffset(days=round(years * 365.25))

    frames = {}
    failures = {}
    for t in requested:
        cache = cache_root / f"{t}.csv"
        df = None
        if cache.exists():
            try:
                df = pd.read_csv(cache, index_col=0, parse_dates=True)
                df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
            except (OSError, ValueError, pd.errors.ParserError):
                df = None
        cached_from = df.index.min() if df is not None and not df.empty else None
        cached_through = df.index.max() if df is not None and not df.empty else None
        cache_covers_window = (
            cached_from is not None
            and cached_through is not None
            and cached_from <= start + timedelta(days=7)
            and cached_through >= end - timedelta(days=7)
        )
        if not cache_covers_window:
            try:
                raw = yf.download(
                    t,
                    start=start,
                    end=end + timedelta(days=1),
                    auto_adjust=True,
                    progress=False,
                    threads=False,
                )
                if raw.empty:
                    failures[t] = "no rows returned"
                    continue
                if isinstance(raw.columns, pd.MultiIndex):
                    raw.columns = raw.columns.get_level_values(0)
                df = raw[["Close"]].rename(columns={"Close": t})
                df.index = pd.to_datetime(df.index, utc=True).tz_convert(None)
                df.to_csv(cache)
            except Exception as exc:
                failures[t] = type(exc).__name__
                continue
        if df is None or df.empty:
            failures[t] = "empty cache"
            continue
        series = df[t] if t in df.columns else df.iloc[:, 0]
        series = pd.to_numeric(series, errors="coerce")
        series = series[(series.index >= start) & (series.index <= end)].dropna()
        if series.empty:
            failures[t] = f"no rows on or before {end.date()}"
            continue
        frames[t] = series

    if failures:
        detail = ", ".join(f"{ticker} ({reason})" for ticker, reason in failures.items())
        raise RuntimeError(f"Missing required price history: {detail}")

    out = pd.concat(frames, axis=1).sort_index().reindex(columns=requested)
    out = out.dropna(how="all")
    out = out.loc[(out.index >= start) & (out.index <= end)]
    out.attrs["requested_as_of"] = end.date().isoformat()
    out.attrs["data_through"] = out.index.max().date().isoformat()
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--years", type=float, default=10.0)
    parser.add_argument("--as-of", default=None)
    args = parser.parse_args()
    p = fetch_prices(args.tickers.split(","), args.years, args.as_of)
    print(p.tail())
