import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from deposit_check import ensure_sufficient_deposit, read_balance


class BalancePage:
    def __init__(self, text):
        self.text = text

    def inner_text(self, selector):
        assert selector == 'body'
        return self.text


class BrokenPage:
    def inner_text(self, selector):
        raise RuntimeError('frame detached')


def test_insufficient_deposit_reports_amounts():
    with pytest.raises(RuntimeError, match='예치금 부족: 보유 500원 / 필요 5,000원'):
        ensure_sufficient_deposit(BalancePage('보유중인 예치금 충전\n500 원\n결제 예정금액 5,000 원'))


def test_sufficient_deposit_allows_purchase():
    ensure_sufficient_deposit(BalancePage('보유중인 예치금 충전 5,000 원'))


def test_zero_deposit_is_insufficient():
    with pytest.raises(RuntimeError, match='예치금 부족: 보유 0원'):
        ensure_sufficient_deposit(BalancePage('보유중인 예치금 충전 0 원'))


def test_missing_deposit_does_not_treat_other_amounts_as_balance():
    ensure_sufficient_deposit(BalancePage('당첨금 500 원 결제 예정금액 5,000 원'))


def test_required_amount_follows_count():
    with pytest.raises(RuntimeError, match='필요 3,000원'):
        ensure_sufficient_deposit(BalancePage('예치금 잔액 2,000원'), count=3)
    ensure_sufficient_deposit(BalancePage('예치금 잔액 3,000원'), count=3)


def test_falls_back_to_next_target():
    # iframe엔 잔액 없음 → 상위 페이지 잔액으로 판정
    with pytest.raises(RuntimeError, match='보유 1,000원'):
        ensure_sufficient_deposit(BalancePage('예치금 충전하기'), BalancePage('보유 예치금 1,000원'))


def test_unreadable_target_is_skipped():
    assert read_balance(BrokenPage()) is None
    ensure_sufficient_deposit(BrokenPage(), BalancePage('보유 예치금 10,000원'))
