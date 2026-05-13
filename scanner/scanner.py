"""
Tydeflow auto-scanner — runs daily via GitHub Actions.
Fetches S&P 500 + Nasdaq 100, filters to $8-$999, scores each symbol,
writes signals to Google Sheets, emails HC hits via Resend.
"""
from __future__ import annotations
import json
import os
import sys
import time as time_module
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

from indicators import score_daily
from notifications import write_signal_to_sheet, send_hc_email, ensure_sheet_setup

# --- Config ---
PRICE_MIN = 8.0
PRICE_MAX = 999.0
COOLDOWN_HOURS = 24          # skip email if symbol alerted within this window
SENSITIVITY = "balanced"
STATE_FILE = Path(__file__).parent / "last_signals.json"


_WIKI_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; Tydeflow-Scanner/1.0; +https://tydeflow.app)"}


def _wiki_tables(url: str) -> list:
    import requests as req
    resp = req.get(url, headers=_WIKI_HEADERS, timeout=20)
    resp.raise_for_status()
    return pd.read_html(resp.text, flavor="lxml")


def get_universe() -> list[str]:
    """Return deduplicated list of S&P 500 + Nasdaq 100 tickers."""
    symbols: set[str] = set()
    try:
        sp500 = _wiki_tables("https://en.wikipedia.org/wiki/List_of_S%26P_500_companies")
        symbols.update(
            sp500[0]["Symbol"].str.replace(".", "-", regex=False).tolist()
        )
    except Exception as e:
        print(f"[warn] S&P 500 fetch failed: {e}")
    try:
        for t in _wiki_tables("https://en.wikipedia.org/wiki/Nasdaq-100"):
            if "Ticker" in t.columns:
                symbols.update(t["Ticker"].dropna().tolist())
                break
    except Exception as e:
        print(f"[warn] Nasdaq 100 fetch failed: {e}")
    return sorted(symbols)


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def within_cooldown(symbol: str, state: dict) -> bool:
    last = state.get(symbol)
    if not last:
        return False
    last_dt = datetime.fromisoformat(last)
    return (datetime.now(timezone.utc) - last_dt) < timedelta(hours=COOLDOWN_HOURS)


def download_batch(symbols: list[str], period: str = "2y") -> dict[str, pd.DataFrame]:
    """Download daily OHLCV for all symbols in one yfinance call."""
    print(f"[info] Downloading {len(symbols)} symbols …")
    raw = yf.download(
        symbols,
        period=period,
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    result: dict[str, pd.DataFrame] = {}
    for sym in symbols:
        try:
            df = raw[sym].dropna(how="all")
            if len(df) >= 55:
                result[sym] = df
        except Exception:
            pass
    print(f"[info] Usable data for {len(result)} symbols")
    return result


def filter_by_price(data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Keep only symbols whose last close is in [$PRICE_MIN, $PRICE_MAX]."""
    filtered = {}
    for sym, df in data.items():
        last_price = float(df["Close"].iloc[-1])
        if PRICE_MIN <= last_price <= PRICE_MAX:
            filtered[sym] = df
    print(f"[info] {len(filtered)} symbols in ${PRICE_MIN:.0f}-${PRICE_MAX:.0f} range")
    return filtered


def main() -> None:
    resend_key = os.environ.get("RESEND_API_KEY", "")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", "")
    sheet_id = os.environ.get("SIGNALS_SHEET_ID", "")

    dry_run = not resend_key or not creds_json or not sheet_id
    if dry_run:
        print("[warn] One or more secrets missing — running in dry-run mode (no email/sheets)")

    state = load_state()
    now_iso = datetime.now(timezone.utc).isoformat()

    # Download SPY for RS calculation
    print("[info] Fetching SPY …")
    spy_df = yf.download("SPY", period="2y", interval="1d", auto_adjust=True, progress=False)
    spy_close: pd.Series | None = spy_df["Close"].dropna() if not spy_df.empty else None

    # Universe
    symbols = get_universe()
    if not symbols:
        print("[error] No symbols fetched — aborting")
        sys.exit(1)

    # Download in one batch (yfinance handles rate limiting internally)
    all_data = download_batch(symbols)
    filtered = filter_by_price(all_data)

    signals = []
    entry_count = 0
    hc_count = 0

    for sym, df in filtered.items():
        try:
            result = score_daily(df, spy_close=spy_close, sensitivity=SENSITIVITY)
            if result is None:
                continue
            result.symbol = sym

            if result.state != "ENTRY":
                continue

            entry_count += 1
            signal_type = "HC_ENTRY" if result.high_conviction else "ENTRY"
            if result.high_conviction:
                hc_count += 1

            signal = {
                "fired_at": now_iso,
                "symbol": sym,
                "timeframe": "1D",
                "signal_type": signal_type,
                "score": result.score,
                "tier": result.tier,
                "rare_count": result.rare_count,
                "detectors": result.detectors,
                "cf_pos": result.cf_pos,
                "price": round(result.price, 2),
            }
            signals.append(signal)

            print(
                f"  {'[HC]' if result.high_conviction else '[EN]'} {sym:6s}  "
                f"score={result.score:+.0f}  rare={result.rare_count}  "
                f"price=${result.price:.2f}  det={result.detectors}"
            )
        except Exception as e:
            print(f"[warn] {sym}: {e}")

    print(f"\n[result] {entry_count} ENTRY signals ({hc_count} HC) from {len(filtered)} symbols scanned")

    if not signals:
        print("[info] No signals this run — nothing to write")
        return

    # Ensure sheet is formatted on first run (idempotent)
    if not dry_run:
        try:
            ensure_sheet_setup(sheet_id, creds_json)
        except Exception as e:
            print(f"[warn] Sheet setup failed: {e}")

    for signal in signals:
        sym = signal["symbol"]

        # Always write to Sheets
        if not dry_run:
            try:
                write_signal_to_sheet(signal, sheet_id, creds_json)
            except Exception as e:
                print(f"[warn] Sheets write failed for {sym}: {e}")
            time_module.sleep(0.5)  # avoid Sheets API rate limit

        # Email only HC signals not in cooldown
        if signal["signal_type"] == "HC_ENTRY":
            if within_cooldown(sym, state):
                print(f"[skip] {sym} HC email skipped — within {COOLDOWN_HOURS}h cooldown")
            else:
                if not dry_run:
                    try:
                        send_hc_email(signal, resend_key)
                        print(f"[email] Sent HC alert for {sym}")
                    except Exception as e:
                        print(f"[warn] Email failed for {sym}: {e}")
                else:
                    print(f"[dry-run] Would email HC alert for {sym}")
                state[sym] = now_iso

    save_state(state)
    print("[done] Scanner complete")


if __name__ == "__main__":
    main()
