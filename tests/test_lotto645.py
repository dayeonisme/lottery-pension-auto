import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lotto645_runner import check_prize


def test_1st_prize():
    assert check_prize([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], 7) == {'rank': '1st', 'prize': 0}


def test_2nd_prize():
    assert check_prize([1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 6], 7) == {'rank': '2nd', 'prize': 0}


def test_3rd_prize():
    assert check_prize([1, 2, 3, 4, 5, 9], [1, 2, 3, 4, 5, 6], 7) == {'rank': '3rd', 'prize': 0}


def test_4th_prize():
    assert check_prize([1, 2, 3, 4, 9, 10], [1, 2, 3, 4, 5, 6], 7) == {'rank': '4th', 'prize': 50000}


def test_5th_prize():
    assert check_prize([1, 2, 3, 9, 10, 11], [1, 2, 3, 4, 5, 6], 7) == {'rank': '5th', 'prize': 5000}


def test_no_prize_two_match():
    assert check_prize([1, 2, 9, 10, 11, 12], [1, 2, 3, 4, 5, 6], 7) == {'rank': 'no prize', 'prize': 0}


def test_no_prize_zero_match():
    assert check_prize([10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6], 7) == {'rank': 'no prize', 'prize': 0}


def test_desktop_insufficient_deposit_stops_before_purchase_attempt(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    import lotto645_runner as runner

    monkeypatch.setenv('DHLOTTERY_ID', 'test')
    monkeypatch.setenv('DHLOTTERY_PW', 'test')
    monkeypatch.setattr(runner, 'ensure_logged_in', lambda page: None)
    monkeypatch.setattr(runner, 'wait_after_login_click', lambda page: None)
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    page = MagicMock()
    page.url = 'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40'
    frame = page.query_selector.return_value.content_frame.return_value
    frame.inner_text.return_value = '보유 예치금 500 원'
    before_buy = MagicMock()

    with pytest.raises(RuntimeError, match='예치금 부족'):
        runner.purchase_tickets(page, before_buy=before_buy)

    before_buy.assert_not_called()
    assert not any(call.args == ('#btnBuy',) for call in frame.click.call_args_list)


def test_mobile_insufficient_deposit_stops_before_purchase_attempt(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    import lotto645_runner as runner

    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    page = MagicMock()
    page.context.cookies.return_value = []
    page.url = 'https://ol.dhlottery.co.kr/olotto/game_mobile/game645.do'
    page.inner_text.return_value = '보유 예치금 500 원'
    before_buy = MagicMock()

    with pytest.raises(RuntimeError, match='예치금 부족'):
        runner._purchase_mobile_lotto645(page, before_buy=before_buy)

    before_buy.assert_not_called()
    assert not any(call.args == ('#btnBuy',) for call in page.click.call_args_list)
