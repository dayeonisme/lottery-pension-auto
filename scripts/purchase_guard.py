"""
purchase_guard.py
중복 구매 방지 — n8n이 같은 날 여러 번(10·11·14시) runner를 실행해도 한 추첨일에 한 번만 구매한다.
- already_purchased: purchases.json에 해당 draw_date 엔트리가 있으면 이미 구매 완료.
- mark_buy_attempt / buy_attempted: 최종 구매 버튼 클릭 직전에 last_run.json에 draw_date를 기록.
  구매 버튼 클릭 후 실패하면 실제 구매 여부가 불확실하므로, 재실행 시 자동 구매하지 않는다.
"""

import json
from pathlib import Path

_ATTEMPT_KEY = 'buy_attempt_draw_date'


def already_purchased(purchases_path: Path, lottery_type: str, draw_date: str) -> bool:
    data = json.loads(purchases_path.read_text(encoding='utf-8'))
    return any(e.get('draw_date') == draw_date for e in data.get(lottery_type, []))


def buy_attempted(last_run_path: Path, lottery_type: str, draw_date: str) -> bool:
    data = json.loads(last_run_path.read_text(encoding='utf-8'))
    return data.get(lottery_type, {}).get(_ATTEMPT_KEY) == draw_date


def mark_buy_attempt(last_run_path: Path, lottery_type: str, draw_date: str) -> None:
    data = json.loads(last_run_path.read_text(encoding='utf-8'))
    data.setdefault(lottery_type, {})[_ATTEMPT_KEY] = draw_date
    last_run_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
