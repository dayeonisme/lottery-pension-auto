#!/usr/bin/env python3
"""
monthly_report.py
매월 1일 실행: 지난달(KST) 구매/당첨 결산을 Google Sheets raw 시트에서 집계해 Telegram으로 발송.
Usage: monthly_report.py [--month YYYY-MM] [--dry-run]
"""

import re
import sys
import json
import logging
import argparse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
import os

sys.path.insert(0, str(Path(__file__).parent))

KST = timezone(timedelta(hours=9))
LOTTERY_ORDER = [('로또6/45', '🎱'), ('연금복권720+', '🎫')]
RANK_ORDER = ['1등', '2등', '3등', '4등', '5등', '6등', '7등', '보너스']


def send_telegram(message: str):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        logging.warning('Telegram credentials not set, skipping notification')
        return
    try:
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        data = json.dumps({'chat_id': chat_id, 'text': message}).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logging.warning('Telegram notification failed: %s', e)


def previous_month(now: datetime) -> str:
    first = now.replace(day=1)
    return (first - timedelta(days=1)).strftime('%Y-%m')


def _to_int(v) -> int:
    s = re.sub(r'[^\d]', '', str(v))
    return int(s) if s else 0


def summarize(rows: list, month: str) -> dict:
    """rows: raw 시트 행(A~K).
    구매는 purchase_datetime(B) 기준, 당첨은 draw_confirmed_date(K) 기준으로 month(YYYY-MM) 집계.
    → 월말 구매분이 다음 달에 당첨 확인되면 다음 달 결산에 포함되어 누락이 없다."""
    out = {name: {'sessions': set(), 'tickets': 0, 'amount': 0, 'ranks': {}, 'prize': 0}
           for name, _ in LOTTERY_ORDER}
    for row in rows:
        row = list(row) + [''] * (11 - len(row))
        name, purchased, result, confirmed = row[0], row[1], row[7], row[10]
        if name not in out:
            continue
        s = out[name]
        if purchased.startswith(month):
            s['sessions'].add(purchased)
            s['tickets'] += 1
            s['amount'] += _to_int(row[5])
        if result == 'win' and confirmed.startswith(month):
            rank = row[8]
            s['ranks'][rank] = s['ranks'].get(rank, 0) + 1
            s['prize'] += _to_int(row[9])
    for s in out.values():
        s['sessions'] = len(s['sessions'])
    return out


def format_report(month: str, summary: dict) -> str:
    y, m = month.split('-')
    lines = [f'📊 {y}년 {int(m)}월 결산']
    total_amount = total_prize = 0
    for name, icon in LOTTERY_ORDER:
        s = summary[name]
        total_amount += s['amount']
        total_prize += s['prize']
        lines += ['', f'{icon} {name}',
                  f'  구매: {s["sessions"]}회 ({s["tickets"]}장) / {s["amount"]:,}원']
        wins = sum(s['ranks'].values())
        if wins:
            ordered = sorted(s['ranks'], key=lambda r: RANK_ORDER.index(r) if r in RANK_ORDER else 99)
            lines.append(f'  당첨: {wins}건')
            lines += [f'    - {r}: {s["ranks"][r]}건' for r in ordered]
        else:
            lines.append('  당첨: 0건')
        lines.append(f'  당첨금: {s["prize"]:,}원')
    lines += ['', f'💰 총 구매 {total_amount:,}원 / 총 당첨 {total_prize:,}원 / 손익 {total_prize - total_amount:+,}원',
              '※ 당첨은 당첨 확인일 기준 집계. 상위 등수(로또 1~3등, 연금 1·2등·보너스) 당첨금은 시트에 미기록 시 합계에서 제외']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--month', help='집계 대상 월 YYYY-MM (기본: 지난달)')
    p.add_argument('--dry-run', action='store_true', help='Telegram 발송 없이 출력만')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

    month = args.month or previous_month(datetime.now(KST))
    from google_sheets import fetch_raw_rows
    message = format_report(month, summarize(fetch_raw_rows(), month))
    print(message)
    if not args.dry_run:
        send_telegram(message)


if __name__ == '__main__':
    main()
