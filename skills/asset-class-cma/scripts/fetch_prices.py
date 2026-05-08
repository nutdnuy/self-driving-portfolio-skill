"""Fetch adjusted-close price history via yfinance, with simple disk caching."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yfinance as yf

_CACHE = Path(".cache/prices")


def fetch_prices(tickers: list[str], years: float = 10.0) -> pd.DataFrame:
    """Return a wide DataFrame of adjusted closes (one column per ticker)."""
    _CACHE.mkdir(parents=True, exist_ok=True)
    end = pd.Timestamp.today().normalize()
    start = end - pd.DateOffset(years=int(years))

    frames = {}
    for t in tickers:
        cache = _CACHE / f"{t}.csv"
        df = None
        if cache.exists():
            try:
                df = pd.read_csv(cache, index_col=0, parse_dates=True)
            except Exception:
                df = None
        if df is None or df.index.max() < (end - pd.Timedelta(days=5)):
            raw = yf.download(
                t, start=start, end=end + pd.Timedelta(days=1),
                auto_adjust=True, progress=False,
            )
            if raw.empty:
                print(f"[fetch_prices] WARN: no data for {t}")
                continue
            if isinstance(raw.columns, pd.MultiIndex):
                raw.columns = raw.columns.get_level_values(0)
            df = raw[["Close"]].rename(columns={"Close": t})
            df.to_csv(cache)
        frames[t] = df[t] if t in df.columns else df.iloc[:, 0]

    out = pd.concat(frames, axis=1).sort_index()
    out = out.dropna(how="all")
    out = out.loc[out.index >= start]
    return out


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--tickers", required=True)
    parser.add_argument("--years", type=float, default=10.0)
    args = parser.parse_args()
    p = fetch_prices(args.tickers.split(","), args.years)
    print(p.tail())
