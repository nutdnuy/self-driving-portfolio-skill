"""Fetch macro indicators from FRED.

Uses the public CSV endpoint by default — no API key required.
If FRED_API_KEY is set, uses the JSON API for higher reliability.
"""
from __future__ import annotations

import io
import os
from datetime import date

import pandas as pd
import requests

FRED_SERIES = {
    "INDPRO": "growth",          # industrial production
    "CPIAUCSL": "inflation",     # CPI
    "DFF": "fedfunds",           # effective fed funds rate
    "T10Y3M": "term_spread",     # 10y minus 3m
    "NFCI": "fci",               # Chicago Fed financial conditions
}


def _fetch_csv(series_id: str) -> pd.Series:
    url = (
        "https://fred.stlouisfed.org/graph/fredgraph.csv"
        f"?id={series_id}"
    )
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    df = pd.read_csv(io.StringIO(r.text))
    df.columns = [c.strip() for c in df.columns]
    date_col = df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.set_index(date_col)
    s = pd.to_numeric(df[series_id], errors="coerce").dropna()
    s.name = series_id
    return s


def _fetch_api(series_id: str, api_key: str, as_of: str) -> pd.Series:
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_end": as_of,
        "realtime_start": as_of,
        "realtime_end": as_of,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    obs = r.json()["observations"]
    df = pd.DataFrame(obs)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    s = pd.to_numeric(df["value"], errors="coerce").dropna()
    s.name = series_id
    return s


def _normalise_as_of(as_of: date | str | None) -> pd.Timestamp:
    cutoff = pd.Timestamp(as_of or date.today()).normalize()
    if cutoff.tzinfo is not None:
        cutoff = cutoff.tz_localize(None)
    if cutoff.date() > date.today():
        raise ValueError(f"as_of cannot be in the future: {cutoff.date()}")
    return cutoff


def fetch_indicators(as_of: date | str | None = None) -> pd.DataFrame:
    """Fetch every required indicator and apply an explicit information cutoff.

    Use a true FRED vintage cutoff when ``FRED_API_KEY`` is available. The
    public CSV fallback can enforce observation dates but contains the latest
    revisions; expose that limitation through ``DataFrame.attrs``.
    """
    cutoff = _normalise_as_of(as_of)
    api_key = os.getenv("FRED_API_KEY", "").strip()
    series = {}
    failures = {}
    for sid in FRED_SERIES:
        try:
            series[sid] = (
                _fetch_api(sid, api_key, cutoff.date().isoformat())
                if api_key
                else _fetch_csv(sid)
            )
        except Exception as exc:
            # Do not include request URLs: authenticated FRED URLs contain the key.
            failures[sid] = type(exc).__name__
    if failures:
        detail = ", ".join(f"{sid} ({kind})" for sid, kind in sorted(failures.items()))
        raise RuntimeError(f"Failed to fetch required FRED series: {detail}")

    df = pd.concat(series, axis=1).sort_index().ffill()
    df = df[df.index <= cutoff]
    if df.empty:
        raise RuntimeError(f"FRED returned no observations on or before {cutoff.date()}")
    empty_columns = [column for column in FRED_SERIES if df[column].dropna().empty]
    if empty_columns:
        raise RuntimeError(f"Required FRED series have no usable observations: {empty_columns}")
    df.attrs["requested_as_of"] = cutoff.date().isoformat()
    df.attrs["vintage_policy"] = (
        "fred_vintage_as_of" if api_key else "latest_revision_cutoff"
    )
    return df


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--as-of", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    df = fetch_indicators(args.as_of)
    print(df.tail())
    if args.out:
        df.to_csv(args.out)
        print(f"wrote {args.out}")
