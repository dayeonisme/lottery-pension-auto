#!/usr/bin/env python3
"""Quick status check — did automation run as expected?"""

import json
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
DATA = ROOT / "data"
KST = timezone(timedelta(hours=9))


def kst_now():
    return datetime.now(KST)


def last_saturday(ref=None):
    d = ref or kst_now()
    days_since = (d.weekday() - 5) % 7  # 5=Saturday
    return (d - timedelta(days=days_since)).replace(hour=0, minute=0, second=0, microsecond=0)


def last_thursday(ref=None):
    d = ref or kst_now()
    days_since = (d.weekday() - 3) % 7  # 3=Thursday
    return (d - timedelta(days=days_since)).replace(hour=0, minute=0, second=0, microsecond=0)


def expected_lotto645_round(last_known_round, last_known_draw_date_str):
    """Estimate current round from last known draw date."""
    last_draw = datetime.strptime(last_known_draw_date_str, "%Y-%m-%d").replace(tzinfo=KST)
    last_sat = last_saturday()
    weeks = (last_sat - last_draw).days // 7
    return last_known_round + max(weeks, 0)


def expected_pension720_round(last_known_round, last_known_draw_date_str):
    last_draw = datetime.strptime(last_known_draw_date_str, "%Y-%m-%d").replace(tzinfo=KST)
    last_thu = last_thursday()
    weeks = (last_thu - last_draw).days // 7
    return last_known_round + max(weeks, 0)


def check():
    now = kst_now()
    print(f"=== 자동화 상태 확인 === {now.strftime('%Y-%m-%d %H:%M KST')}\n")

    last_run = json.loads((DATA / "last_run.json").read_text())
    lotto_data = json.loads((DATA / "lotto645_purchases.json").read_text())["lotto645"]
    pension_data = json.loads((DATA / "pension720_purchases.json").read_text())["pension720"]

    # ── Lotto 6/45 ──────────────────────────────────────────────────────────
    lr = last_run["lotto645"]
    last_purchase = lotto_data[-1] if lotto_data else None
    last_purchased_round = last_purchase["round"] if last_purchase else 0
    last_draw_date = last_purchase["draw_date"] if last_purchase else "2026-01-01"
    exp_round = expected_lotto645_round(last_purchased_round, last_draw_date)

    print("▶ 로또 6/45")
    print(f"  마지막 실행 : {lr['last_run']}")
    print(f"  상태        : {lr['status']}")
    print(f"  마지막 구매 : {last_purchased_round}회 ({last_purchase['purchase_date'] if last_purchase else '-'})")
    print(f"  예상 최신   : {exp_round}회 (지난 토요일 기준)")
    missed = exp_round - last_purchased_round
    if missed > 0:
        print(f"  ⚠️  {missed}회 미구매")
    else:
        print("  ✅ 최신")

    unchecked_lotto = [e for e in lotto_data if not e["result"]["checked"]]
    if unchecked_lotto:
        print(f"  미확인 당첨: {len(unchecked_lotto)}건 (회차: {[e['round'] for e in unchecked_lotto]})")
    else:
        print("  당첨 확인  : 모두 완료")

    if last_purchase and len(last_purchase.get("tickets", [])) < 5:
        print(f"  ⚠️  최근 구매 티켓 {len(last_purchase['tickets'])}장 (5장 미달)")

    if lr["pending_sheets_round"]:
        print(f"  ⚠️  Sheets 미기록 회차: {lr['pending_sheets_round']}")

    print()

    # ── Pension 720+ ─────────────────────────────────────────────────────────
    pr = last_run["pension720"]
    last_p = pension_data[-1] if pension_data else None
    last_p_round = last_p["round"] if last_p else 0
    last_p_draw = last_p["draw_date"] if last_p else "2026-01-01"
    exp_p_round = expected_pension720_round(last_p_round, last_p_draw)

    print("▶ 연금복권 720+")
    print(f"  마지막 실행 : {pr['last_run']}")
    print(f"  상태        : {pr['status']}")
    print(f"  마지막 구매 : {last_p_round}회 ({last_p['purchase_date'] if last_p else '-'})")
    print(f"  예상 최신   : {exp_p_round}회 (지난 목요일 기준)")
    missed_p = exp_p_round - last_p_round
    if missed_p > 0:
        print(f"  ⚠️  {missed_p}회 미구매")
    else:
        print("  ✅ 최신")

    unchecked_p = [e for e in pension_data if not e["result"]["checked"]]
    if unchecked_p:
        print(f"  미확인 당첨: {len(unchecked_p)}건 (회차: {[e['round'] for e in unchecked_p]})")
    else:
        print("  당첨 확인  : 모두 완료")

    if pr["pending_sheets_round"]:
        print(f"  ⚠️  Sheets 미기록 회차: {pr['pending_sheets_round']}")

    print()
    print("락 파일:")
    for lock in DATA.glob("*.lock"):
        mtime = datetime.fromtimestamp(lock.stat().st_mtime, tz=KST)
        print(f"  ⚠️  {lock.name} (생성: {mtime.strftime('%Y-%m-%d %H:%M KST')})")
    else:
        if not list(DATA.glob("*.lock")):
            print("  없음 (정상)")


if __name__ == "__main__":
    check()
