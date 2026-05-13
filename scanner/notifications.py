"""Email via Resend and Google Sheets write for Tydeflow scanner signals."""
from __future__ import annotations
import json
import os
from datetime import datetime, timezone

import gspread
import resend
from google.oauth2.service_account import Credentials

SHEET_COLUMNS = [
    "Fired At", "Symbol", "Timeframe", "Type", "Score",
    "Tier", "Rare Detectors", "Detector Names", "CF Factors", "Price",
]

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


def _sheets_client(creds_json: str):
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)


def ensure_sheet_header(sheet_id: str, creds_json: str) -> None:
    """Write column headers to row 1 if the sheet is empty."""
    gc = _sheets_client(creds_json)
    ws = gc.open_by_key(sheet_id).sheet1
    if ws.row_count == 0 or ws.acell("A1").value != "Fired At":
        ws.insert_row(SHEET_COLUMNS, index=1)


def write_signal_to_sheet(signal: dict, sheet_id: str, creds_json: str) -> None:
    gc = _sheets_client(creds_json)
    ws = gc.open_by_key(sheet_id).sheet1
    row = [
        signal["fired_at"],
        signal["symbol"],
        signal["timeframe"],
        signal["signal_type"],
        signal["score"],
        signal["tier"],
        signal["rare_count"],
        ", ".join(signal.get("detectors", [])) or "—",
        signal["cf_pos"],
        signal["price"],
    ]
    ws.append_row(row, value_input_option="USER_ENTERED")


def _email_html(signal: dict) -> str:
    score_str = f"+{signal['score']}" if signal["score"] >= 0 else str(signal["score"])
    detectors_str = ", ".join(signal.get("detectors", [])) or "—"
    tv_url = f"https://www.tradingview.com/chart/?symbol={signal['symbol']}"
    tier_label = {"S": "Short-term", "M": "Medium-term", "L": "Long-term"}.get(signal["tier"], signal["tier"])
    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{ font-family: 'Courier New', monospace; background: #0a0a0a; color: #e0e0e0; margin: 0; padding: 32px; }}
  .card {{ background: #111; border: 1px solid #2a2a2a; border-radius: 8px; padding: 28px 32px; max-width: 520px; margin: 0 auto; }}
  .label {{ color: #555; font-size: 11px; letter-spacing: 0.12em; text-transform: uppercase; }}
  .symbol {{ font-size: 42px; font-weight: 700; color: #fff; margin: 6px 0 2px; letter-spacing: 0.04em; }}
  .badge {{ display: inline-block; background: #00b4d8; color: #fff; font-size: 11px; font-weight: 700;
            padding: 3px 10px; border-radius: 4px; letter-spacing: 0.1em; margin-bottom: 20px; }}
  .row {{ display: flex; justify-content: space-between; border-top: 1px solid #1e1e1e; padding: 10px 0; }}
  .val {{ color: #5ec896; font-size: 15px; }}
  .val-dim {{ color: #9b9b9b; font-size: 14px; }}
  .btn {{ display: block; text-align: center; margin-top: 24px; padding: 12px;
          background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 6px;
          color: #5ec896; text-decoration: none; font-size: 13px; letter-spacing: 0.06em; }}
  .footer {{ text-align: center; color: #333; font-size: 11px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="card">
  <div class="label">Tydeflow Scanner</div>
  <div class="symbol">{signal["symbol"]}</div>
  <div class="badge">&#9670; HIGH CONVICTION ENTRY</div>
  <div class="row">
    <span class="label">Score</span>
    <span class="val">{score_str}</span>
  </div>
  <div class="row">
    <span class="label">Timeframe</span>
    <span class="val-dim">{signal["timeframe"]}</span>
  </div>
  <div class="row">
    <span class="label">Price</span>
    <span class="val-dim">${signal["price"]:.2f}</span>
  </div>
  <div class="row">
    <span class="label">Tier</span>
    <span class="val-dim">{tier_label}</span>
  </div>
  <div class="row">
    <span class="label">Rare detectors</span>
    <span class="val-dim">{detectors_str}</span>
  </div>
  <div class="row">
    <span class="label">Confluence factors</span>
    <span class="val-dim">{signal["cf_pos"]} / 5</span>
  </div>
  <a href="{tv_url}" class="btn">Open chart on TradingView &rarr;</a>
</div>
<div class="footer">Tydeflow &middot; Daily scan &middot; {signal["fired_at"][:10]}</div>
</body>
</html>"""


def send_hc_email(signal: dict, api_key: str, to: str = "tyler@tydeflow.app") -> None:
    resend.api_key = api_key
    score_str = f"+{signal['score']}" if signal["score"] >= 0 else str(signal["score"])
    resend.Emails.send({
        "from": "Tydeflow Signals <signals@tydeflow.app>",
        "to": [to],
        "subject": f"HC ENTRY — {signal['symbol']} 1D  |  Score {score_str}  |  {signal['rare_count']} rare detector{'s' if signal['rare_count'] != 1 else ''}",
        "html": _email_html(signal),
    })
