"""
google_sheets.py
Google Sheets helper using service account auth (gspread 6.x).
"""

import re
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

import gspread

ROOT = Path(__file__).parent.parent
SERVICE_ACCOUNT_PATH = Path(os.environ.get('GOOGLE_SERVICE_ACCOUNT_PATH', ROOT / 'config' / 'service_account.json'))
SPREADSHEET_ID = os.environ.get('GOOGLE_SPREADSHEET_ID')
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# Google Sheets A열 값 — 기존 데이터와 반드시 일치
LOTTERY_DISPLAY_NAME = {
    'lotto645': '로또6/45',
    'pension720': '연금복권720+',
}

KST = timezone(timedelta(hours=9))


def _now_kst_str() -> str:
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


def _today_kst() -> str:
    return datetime.now(KST).strftime('%Y-%m-%d')


_client: gspread.Client = None


def get_client() -> gspread.Client:
    global _client
    if not SPREADSHEET_ID:
        raise RuntimeError('GOOGLE_SPREADSHEET_ID is not set')
    if _client is None:
        _client = gspread.service_account(filename=SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return _client


def update_prize_results(lottery_type: str, round_no: int, ticket_results: list, purchase_date: str = None) -> int:
    """raw 시트에서 lottery_type + round_no 행을 찾아 H~K 열 업데이트.
    purchase_date 지정 시 column B(purchase_datetime)도 매칭 — 동일 회차 복수 구매 세션 구분.
    반환: 업데이트된 행 수."""
    client = get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet('raw')

    all_values = ws.get_all_values()
    display_name = LOTTERY_DISPLAY_NAME.get(lottery_type, lottery_type)
    today = _today_kst()

    updates = []
    for i, row in enumerate(all_values[1:], start=2):  # 1행은 헤더, 시트 행은 2부터
        if len(row) < 4:
            continue
        if row[0] == display_name and str(row[2]) == str(round_no):
            if purchase_date is not None and row[1] != purchase_date:
                continue  # 동일 회차 내 다른 구매 세션 건너뜀
            ticket_no = int(row[3]) if row[3].isdigit() else 0
            t = next((t for t in ticket_results if t['no'] == ticket_no), None)
            if not t:
                continue
            result_val = 'no prize' if t['rank'] == 'no prize' else 'win'
            rank_val = '-' if t['rank'] == 'no prize' else ('보너스' if t['rank'] == 'bonus' else re.sub(r'(\d+)(st|nd|rd|th)', r'\1등', t['rank']))
            prize_val = t['prize'] if t['prize'] > 0 else '-'
            updates.append({
                'range': f'raw!H{i}:K{i}',
                'values': [[result_val, rank_val, prize_val, today]],
            })

    if updates:
        ws.spreadsheet.values_batch_update({
            'valueInputOption': 'RAW',
            'data': updates,
        })

    return len(updates)


def append_purchase_rows(lottery_type: str, purchase_data: dict) -> None:
    """raw 시트 하단에 티켓 1장당 1행씩 추가."""
    client = get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet('raw')

    display_name = LOTTERY_DISPLAY_NAME.get(lottery_type, lottery_type)

    rows = []
    for ticket in purchase_data['tickets']:
        if lottery_type == 'lotto645':
            numbers_str = ' '.join(str(n).zfill(2) for n in ticket['numbers'])
        else:
            numbers_str = f"{ticket['group']}-{ticket['numbers']}"
        rows.append([
            display_name, purchase_data['purchase_date'], purchase_data['round'], ticket['no'],
            numbers_str, 1000, purchase_data['draw_date'],
            'pending', '-', '-', '-',
        ])

    ws.append_rows(rows, value_input_option=gspread.utils.ValueInputOption.raw)
