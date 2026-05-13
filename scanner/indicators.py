"""
Tydeflow scoring logic ported from pine/tydeflow_flow.pine.
Daily timeframe only — EOD and Opening Range detectors are intraday-only and skipped.
"""
from __future__ import annotations
import pandas as pd
import numpy as np
from dataclasses import dataclass, field


@dataclass
class SignalResult:
    symbol: str
    timeframe: str
    price: float
    score: float
    state: str
    tier: str
    rare_count: int
    high_conviction: bool
    cf_pos: int
    detectors: list[str] = field(default_factory=list)


def _sma(s: pd.Series, n: int) -> pd.Series:
    return s.rolling(n).mean()


def _rsi(s: pd.Series, n: int = 14) -> pd.Series:
    delta = s.diff()
    gain = delta.clip(lower=0)
    loss = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=n - 1, min_periods=n).mean()
    avg_loss = loss.ewm(com=n - 1, min_periods=n).mean()
    rs = avg_gain / avg_loss.replace(0, 1e-10)
    return 100 - (100 / (1 + rs))


def _atr(high: pd.Series, low: pd.Series, close: pd.Series, n: int = 14) -> pd.Series:
    tr = pd.concat([
        high - low,
        (high - close.shift()).abs(),
        (low - close.shift()).abs(),
    ], axis=1).max(axis=1)
    return tr.ewm(com=n - 1, min_periods=n).mean()


def score_daily(
    df: pd.DataFrame,
    spy_close: pd.Series | None = None,
    sensitivity: str = "balanced",
    gap_threshold: float = 1.0,
) -> SignalResult | None:
    """
    Score a single symbol's daily OHLCV DataFrame using Tydeflow logic.

    df must have columns: Open, High, Low, Close, Volume (title-cased).
    Returns None if insufficient data.
    """
    if len(df) < 55:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    open_ = df["Open"]

    # --- Weights (Swing style, fmul=1.10, cmul=0.85) ---
    WA = 1.2 * 1.10
    WV = 1.1 * 1.10
    WP = 1.0 * 1.10
    WT = 1.3 * 1.10

    ethr = 70.0 if sensitivity == "conservative" else (50.0 if sensitivity == "aggressive" else 60.0)
    cf_thr = 4 if sensitivity == "conservative" else (2 if sensitivity == "aggressive" else 3)
    wthr = ethr - 20.0
    cmul = 0.85

    c = float(close.iloc[-1])
    o = float(open_.iloc[-1])

    # --- Confluence ---
    ma50_s = _sma(close, 50)
    ma200_s = _sma(close, 200)
    m50 = float(ma50_s.iloc[-1])
    m200 = float(ma200_s.iloc[-1])

    if np.isnan(m50) or np.isnan(m200):
        return None

    t_stk = c > m50 and m50 > m200
    t_50 = c > m50 and not (m50 > m200)
    t_200 = c > m200 and not (c > m50)
    trend_val = 1.0 if t_stk else (0.6 if t_50 else (-0.4 if t_200 else -1.0))

    rsi14_s = _rsi(close, 14)
    rsi14 = float(rsi14_s.iloc[-1])
    if np.isnan(rsi14):
        return None

    r_sweet = 50 <= rsi14 <= 65
    r_mid = (40 <= rsi14 < 50) or (65 < rsi14 <= 70)
    r_low = 30 <= rsi14 < 40
    rsi_val = 1.0 if r_sweet else (0.5 if r_mid else (0.0 if r_low else (-0.5 if rsi14 > 70 else -0.7)))

    avg30 = volume.rolling(30).mean()
    avg30_last = float(avg30.iloc[-1])
    vol_last = float(volume.iloc[-1])
    rvol = vol_last / avg30_last if avg30_last > 0 else 1.0
    pup = c > o
    rvol_val = 0.8 if (rvol > 1.5 and pup) else (0.4 if (1.0 <= rvol <= 1.5 and pup) else (-0.5 if rvol < 0.7 else 0.0))

    # RS vs SPY: 30-bar return differential
    rs_val = 0.0
    if spy_close is not None and len(close) >= 31 and len(spy_close) >= 31:
        try:
            sr30 = (float(close.iloc[-1]) - float(close.iloc[-31])) / float(close.iloc[-31]) * 100
            sr30spy = (float(spy_close.iloc[-1]) - float(spy_close.iloc[-31])) / float(spy_close.iloc[-31]) * 100
            rsdiff = sr30 - sr30spy
            rs_val = 1.0 if rsdiff >= 10 else (0.5 if rsdiff >= 5 else (0.0 if rsdiff >= -5 else (-0.5 if rsdiff >= -10 else -1.0)))
        except Exception:
            rs_val = 0.0

    hi52_s = high.rolling(252).max()
    hi52 = float(hi52_s.iloc[-1]) if not np.isnan(hi52_s.iloc[-1]) else float(high.max())
    dpct = (hi52 - c) / hi52 * 100 if hi52 > 0 else 0.0
    dist_val = 1.0 if dpct <= 5 else (0.5 if dpct <= 10 else (0.0 if dpct <= 20 else (-0.5 if dpct <= 35 else -1.0)))

    cf_tot = (trend_val + rsi_val + rvol_val + rs_val + dist_val) * cmul
    cf_pos = sum(1 for v in [trend_val, rsi_val, rvol_val, rs_val, dist_val] if v > 0)

    # --- ATR ---
    atr14_s = _atr(high, low, close, 14)
    atr14 = float(atr14_s.iloc[-1])
    if np.isnan(atr14) or atr14 <= 0:
        return None

    # --- Footprint detectors ---

    # 1. Volume Absorption
    fp_abs = 0.0
    body = abs(c - o)
    if vol_last > 2.0 * avg30_last and body < 0.35 * atr14 and avg30_last > 0:
        fp_abs = min(min(rvol / 1.5, 3.0) / 3.0 * 100, 100)

    # 2. VWAP Magnetism — daily approximation: typical price ≈ daily VWAP
    typical = (high + low + close) / 3
    vn_s = (close - typical).abs() < 0.3 * atr14_s
    vvol_s = volume > 1.2 * avg30
    vbars = 0
    for i in range(len(df) - 1, max(len(df) - 30, -1), -1):
        v_ok = bool(vn_s.iloc[i]) if not pd.isna(vn_s.iloc[i]) else False
        vol_ok = bool(vvol_s.iloc[i]) if not pd.isna(vvol_s.iloc[i]) else False
        if v_ok and vol_ok:
            vbars += 1
        else:
            break
    fp_vwap = 0.0
    if vbars >= 8:
        fp_vwap = min(30.0 + (vbars - 8) / 15.0 * 70.0, 100.0)

    # 3. Volume-at-Price Clustering
    fp_vap = 0.0
    if len(df) >= 100:
        rng10 = float(high.iloc[-10:].max() - low.iloc[-10:].min())
        a100 = float(volume.rolling(100).mean().iloc[-1])
        v10 = float(volume.iloc[-10:].sum())
        if a100 > 0 and rng10 < 1.5 * atr14 and v10 > 2.5 * a100 * 10:
            fp_vap = min(
                (1.5 * atr14) / max(rng10, atr14 * 0.1) * (v10 / (a100 * 10) / 2.0) * 30.0,
                100.0,
            )

    # 4. Up/Down Tick Volume Imbalance (close > open = up-tick approximation)
    fp_tick = 0.0
    uv = np.where(close.values > open_.values, volume.values, 0.0)
    dv = np.where(close.values < open_.values, volume.values, 0.0)
    su = float(uv[-20:].sum())
    sd = float(dv[-20:].sum())
    rat = su / sd if sd > 0 else (10.0 if su > 0 else 1.0)
    if rat > 2.2:
        fp_tick = min(50.0 + (rat - 2.2) / 2.0 * 100.0, 100.0)
    elif rat < 0.45:
        fp_tick = -min(50.0 + (0.45 - rat) / 0.4 * 100.0, 100.0)

    # --- Tydeflow Score (Pine lines 217-221) ---
    ustr = fp_abs * WA + fp_vwap * WV + fp_vap * WP
    dir_ = float(np.sign(fp_tick)) if abs(fp_tick) >= 25 else (1.0 if c >= m50 else -1.0)
    tscore = float(np.clip((ustr * dir_ + fp_tick * WT) * 0.6 + cf_tot * 8.0, -100.0, 100.0))

    # Rare detectors (tick NOT in rare_count — Pine line 230)
    fa = fp_abs >= 50
    fv = fp_vwap >= 50
    fp_flag = fp_vap >= 50
    ft = abs(fp_tick) >= 50
    rare_count = (1 if fa else 0) + (1 if fv else 0) + (1 if fp_flag else 0)

    detectors = []
    if fa:
        detectors.append("Absorption")
    if fv:
        detectors.append("VWAP Mag")
    if fp_flag:
        detectors.append("Vol@Price")
    if ft:
        detectors.append("Tick Imbal")

    # --- State machine ---
    stretched_above = rsi14 > 65 and m50 > 0 and (c - m50) / m50 * 100 > 15
    prev_close = float(close.iloc[-2]) if len(df) >= 2 else c
    gap_pct = (o - prev_close) / prev_close * 100 if prev_close > 0 else 0.0
    gap_down_active = gap_pct < -gap_threshold

    ec = tscore > ethr and cf_pos >= cf_thr and rsi14 < 70 and not stretched_above and not gap_down_active
    wc = tscore > wthr and cf_pos >= 2

    state = "ENTRY" if ec else ("WATCH" if wc else "WAIT")
    high_conviction = ec and rare_count >= 1

    # Tier: L = no recent prior entry (scanner default); tracked in scanner.py with last_signals.json
    return SignalResult(
        symbol="",
        timeframe="1D",
        price=c,
        score=round(tscore, 1),
        state=state,
        tier="L",
        rare_count=rare_count,
        high_conviction=high_conviction,
        cf_pos=cf_pos,
        detectors=detectors,
    )
