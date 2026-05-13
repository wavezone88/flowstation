"""Email via Resend and Google Sheets write for Tydeflow scanner signals."""
from __future__ import annotations
import json
from datetime import datetime, timezone, timedelta

import gspread
import resend
from google.oauth2.service_account import Credentials

# Column order in the sheet
SHEET_COLUMNS = ["DATE", "SYMBOL", "TYPE", "SCORE", "PRICE", "TIER", "DETECTORS", "CF", "TF"]
_NUM_COLS = len(SHEET_COLUMNS)
_COL_LAST = "I"  # update if NUM_COLS changes

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# --- Color palette ---
_BG_SHEET   = "#0a0a0a"   # title row bg
_BG_HEADER  = "#111111"   # column header row bg
_BG_HC      = "#001928"   # HC_ENTRY row bg
_BG_ENTRY   = "#0a1a10"   # ENTRY row bg
_FG_GREEN   = "#5ec896"   # Tydeflow green
_FG_CYAN    = "#00b4d8"   # HC accent
_FG_RED     = "#e05555"
_FG_WHITE   = "#ffffff"
_FG_LIGHT   = "#cccccc"
_FG_MID     = "#777777"
_FG_DIM     = "#444444"
_FG_DIMMER  = "#2e2e2e"


def _rgb(hex_color: str) -> dict:
    h = hex_color.lstrip("#")
    return {
        "red":   int(h[0:2], 16) / 255,
        "green": int(h[2:4], 16) / 255,
        "blue":  int(h[4:6], 16) / 255,
    }


def _fmt(bg: str, fg: str, bold=False, italic=False, size=10, align="LEFT") -> dict:
    return {
        "backgroundColor": _rgb(bg),
        "textFormat": {
            "foregroundColor": _rgb(fg),
            "bold": bold,
            "italic": italic,
            "fontSize": size,
        },
        "horizontalAlignment": align,
        "verticalAlignment": "MIDDLE",
        "wrapStrategy": "CLIP",
    }


def _sheets_client(creds_json: str) -> gspread.Client:
    info = json.loads(creds_json)
    creds = Credentials.from_service_account_info(info, scopes=_SCOPES)
    return gspread.authorize(creds)


def _setup_sheet(spreadsheet: gspread.Spreadsheet, ws: gspread.Worksheet) -> None:
    """One-time formatting: column widths, row heights, freeze, title row, tab color."""
    sid = ws.id

    col_widths = [145, 72, 98, 62, 72, 88, 205, 40, 38]
    requests = (
        # Column widths
        [{"updateDimensionProperties": {
            "range": {"sheetId": sid, "dimension": "COLUMNS", "startIndex": i, "endIndex": i + 1},
            "properties": {"pixelSize": w}, "fields": "pixelSize",
        }} for i, w in enumerate(col_widths)]
        +
        # Row heights: title=44, header=30, data rows=26
        [
            {"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 0, "endIndex": 1},
                "properties": {"pixelSize": 44}, "fields": "pixelSize",
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 1, "endIndex": 2},
                "properties": {"pixelSize": 30}, "fields": "pixelSize",
            }},
            {"updateDimensionProperties": {
                "range": {"sheetId": sid, "dimension": "ROWS", "startIndex": 2, "endIndex": 2000},
                "properties": {"pixelSize": 26}, "fields": "pixelSize",
            }},
        ]
        +
        [
            # Merge title row across all columns
            {"mergeCells": {
                "range": {"sheetId": sid, "startRowIndex": 0, "endRowIndex": 1,
                           "startColumnIndex": 0, "endColumnIndex": _NUM_COLS},
                "mergeType": "MERGE_ALL",
            }},
            # Freeze header rows
            {"updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"frozenRowCount": 2}},
                "fields": "gridProperties.frozenRowCount",
            }},
            # Tab color
            {"updateSheetProperties": {
                "properties": {"sheetId": sid, "tabColorStyle": {"rgbColor": _rgb(_FG_GREEN)}},
                "fields": "tabColorStyle",
            }},
            # Hide gridlines
            {"updateSheetProperties": {
                "properties": {"sheetId": sid, "gridProperties": {"hideGridlines": True}},
                "fields": "gridProperties.hideGridlines",
            }},
        ]
    )

    spreadsheet.batch_update({"requests": requests})

    # Title row
    ws.update("A1", [["⬡  TYDEFLOW  ·  DAILY SIGNALS"]])
    ws.format("A1", _fmt(_BG_SHEET, _FG_GREEN, bold=True, size=13, align="CENTER"))

    # Column header row
    ws.update("A2", [SHEET_COLUMNS])
    ws.format(f"A2:{_COL_LAST}2", _fmt(_BG_HEADER, _FG_MID, bold=True, size=9, align="CENTER"))


def _format_data_row(ws: gspread.Worksheet, row_num: int, signal: dict) -> None:
    is_hc    = signal["signal_type"] == "HC_ENTRY"
    row_bg   = _BG_HC if is_hc else _BG_ENTRY
    type_fg  = _FG_CYAN if is_hc else _FG_GREEN
    score_fg = _FG_GREEN if signal.get("score", 0) >= 0 else _FG_RED

    ws.batch_format([
        # Full row base
        {"range": f"A{row_num}:{_COL_LAST}{row_num}",
         "format": _fmt(row_bg, _FG_MID, size=10)},
        # Date (A) — dimmer, smaller
        {"range": f"A{row_num}",
         "format": _fmt(row_bg, _FG_DIM, size=9)},
        # Symbol (B) — bold white, slightly larger
        {"range": f"B{row_num}",
         "format": _fmt(row_bg, _FG_WHITE, bold=True, size=11)},
        # Type (C) — colored, bold
        {"range": f"C{row_num}",
         "format": _fmt(row_bg, type_fg, bold=True, size=10)},
        # Score (D) — colored, bold, centered
        {"range": f"D{row_num}",
         "format": {**_fmt(row_bg, score_fg, bold=True, size=10), "horizontalAlignment": "CENTER"}},
        # Price (E) — light
        {"range": f"E{row_num}",
         "format": _fmt(row_bg, _FG_LIGHT, size=10)},
        # Detectors (G) — italic, dim
        {"range": f"G{row_num}",
         "format": _fmt(row_bg, _FG_DIM, italic=True, size=9)},
        # CF (H) — centered, dim
        {"range": f"H{row_num}",
         "format": {**_fmt(row_bg, _FG_MID, size=9), "horizontalAlignment": "CENTER"}},
        # TF (I) — centered, dimmer
        {"range": f"I{row_num}",
         "format": {**_fmt(row_bg, _FG_DIMMER, size=9), "horizontalAlignment": "CENTER"}},
    ])


def _signal_row_values(signal: dict) -> list:
    """Format signal dict into display-ready row values."""
    fired = datetime.fromisoformat(signal["fired_at"])
    # Convert to ET for display
    et = fired.astimezone(timezone(timedelta(hours=-4)))   # EDT; close enough year-round
    date_str = et.strftime("%-m/%-d  %-I:%M %p").replace("AM", "am").replace("PM", "pm")
    score = signal["score"]
    score_str = f"+{score}" if score >= 0 else str(score)
    type_label = "◆ HC ENTRY" if signal["signal_type"] == "HC_ENTRY" else "▲ ENTRY"
    tier_map = {"L": "Long-term", "M": "Medium-term", "S": "Short-term"}
    detectors = "  ·  ".join(signal.get("detectors", [])) or "—"
    return [
        date_str,
        signal["symbol"],
        type_label,
        score_str,
        f"${signal['price']:.2f}",
        tier_map.get(signal["tier"], signal["tier"]),
        detectors,
        f"{signal['cf_pos']}/5",
        signal["timeframe"],
    ]


def ensure_sheet_setup(sheet_id: str, creds_json: str) -> None:
    """Format the sheet on first run (idempotent — checks A1 for title text)."""
    gc = _sheets_client(creds_json)
    spreadsheet = gc.open_by_key(sheet_id)
    ws = spreadsheet.sheet1

    if ws.acell("A1").value == "⬡  TYDEFLOW  ·  DAILY SIGNALS":
        return  # already set up

    _setup_sheet(spreadsheet, ws)


def write_signal_to_sheet(signal: dict, sheet_id: str, creds_json: str) -> None:
    gc = _sheets_client(creds_json)
    ws = gc.open_by_key(sheet_id).sheet1
    ws.append_row(_signal_row_values(signal), value_input_option="USER_ENTERED")
    row_num = len(ws.get_all_values())  # row we just appended
    _format_data_row(ws, row_num, signal)


# --- Email ---

def _email_html(signal: dict) -> str:
    score = signal["score"]
    score_str = f"+{score}" if score >= 0 else str(score)
    detectors_str = "  ·  ".join(signal.get("detectors", [])) or "—"
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
    <span class="label">Score</span><span class="val">{score_str}</span>
  </div>
  <div class="row">
    <span class="label">Timeframe</span><span class="val-dim">{signal["timeframe"]}</span>
  </div>
  <div class="row">
    <span class="label">Price</span><span class="val-dim">${signal["price"]:.2f}</span>
  </div>
  <div class="row">
    <span class="label">Tier</span><span class="val-dim">{tier_label}</span>
  </div>
  <div class="row">
    <span class="label">Rare detectors</span><span class="val-dim">{detectors_str}</span>
  </div>
  <div class="row">
    <span class="label">Confluence factors</span><span class="val-dim">{signal["cf_pos"]} / 5</span>
  </div>
  <a href="{tv_url}" class="btn">Open chart on TradingView &rarr;</a>
</div>
<div class="footer">Tydeflow &middot; Daily scan &middot; {signal["fired_at"][:10]}</div>
</body>
</html>"""


def send_hc_email(signal: dict, api_key: str, to: str = "tyler@tydeflow.app") -> None:
    resend.api_key = api_key
    score = signal["score"]
    score_str = f"+{score}" if score >= 0 else str(score)
    resend.Emails.send({
        "from": "Tydeflow Signals <signals@tydeflow.app>",
        "to": [to],
        "subject": (
            f"HC ENTRY — {signal['symbol']} 1D  |  Score {score_str}  |  "
            f"{signal['rare_count']} rare detector{'s' if signal['rare_count'] != 1 else ''}"
        ),
        "html": _email_html(signal),
    })
