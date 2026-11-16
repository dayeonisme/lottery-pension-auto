"""
deposit_check.py
구매 화면에서 예치금 잔액을 읽어 부족하면 결제 시도 기록(before_buy) 전에 중단.
예치금 부족이 결제 버튼 클릭 이후 timeout으로 드러나면 purchase_guard가 '구매 불확실'로 막아
충전 후에도 같은 날 재시도(11·14시)가 막힘 → 클릭 전에 명확한 사유로 실패시킨다.
잔액 문구를 못 찾으면 경고만 남기고 기존 흐름 진행(오판으로 구매가 막히지 않도록).
"""

import logging
import re

TICKET_PRICE = 1000

_BALANCE_RE = re.compile(
    r'(?:보유\s*(?:중인\s*)?예치금|예치금\s*잔액)\s*(?:충전\s*)?([\d,]+)\s*원'
)


def read_balance(page_or_frame):
    """body 텍스트에서 예치금 잔액(원)을 읽는다. 못 읽으면 None."""
    try:
        text = page_or_frame.inner_text('body')
    except Exception:
        return None
    match = _BALANCE_RE.search(text)
    return int(match.group(1).replace(',', '')) if match else None


def ensure_sufficient_deposit(*targets, count: int = 5) -> None:
    """targets(page/frame)를 순서대로 보며 처음 읽힌 잔액으로 판정."""
    for target in targets:
        balance = read_balance(target)
        if balance is not None:
            break
    else:
        logging.warning('구매 화면에서 예치금 잔액을 읽지 못함 — 기존 구매 흐름 진행')
        return
    required = TICKET_PRICE * count
    logging.info('예치금 잔액 %s원 / 필요 %s원', f'{balance:,}', f'{required:,}')
    if balance < required:
        raise RuntimeError(
            f'예치금 부족: 보유 {balance:,}원 / 필요 {required:,}원 '
            f'— {required - balance:,}원 이상 충전해 주세요.'
        )
