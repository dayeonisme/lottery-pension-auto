import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from pension720_runner import check_prize


def test_1st_prize():
    # 조 일치 + 번호 완전 일치
    assert check_prize(1, '307710', 1, '307710') == {'rank': '1st', 'prize': 0}


def test_2nd_prize():
    # 조 불일치 + 번호 완전 일치
    assert check_prize(2, '307710', 1, '307710') == {'rank': '2nd', 'prize': 0}


def test_3rd_prize():
    # 뒤 5자리 일치 (앞 1자리 다름)
    assert check_prize(1, '107710', 1, '307710') == {'rank': '3rd', 'prize': 1000000}


def test_4th_prize():
    # 뒤 4자리 일치
    assert check_prize(1, '117710', 1, '307710') == {'rank': '4th', 'prize': 100000}


def test_5th_prize():
    # 뒤 3자리 일치
    assert check_prize(1, '111710', 1, '307710') == {'rank': '5th', 'prize': 50000}


def test_6th_prize():
    # 뒤 2자리 일치
    assert check_prize(1, '111110', 1, '307710') == {'rank': '6th', 'prize': 5000}


def test_7th_prize():
    # 뒤 1자리 일치 (뒤 2자리는 불일치)
    assert check_prize(1, '111100', 1, '307710') == {'rank': '7th', 'prize': 1000}


def test_no_prize():
    assert check_prize(1, '111111', 1, '307712') == {'rank': 'no prize', 'prize': 0}


def test_desktop_insufficient_deposit_stops_before_purchase_attempt(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    import pension720_runner as runner

    monkeypatch.setenv('DHLOTTERY_ID', 'test')
    monkeypatch.setenv('DHLOTTERY_PW', 'test')
    monkeypatch.setattr(runner, 'ensure_logged_in', lambda page: None)
    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    page = MagicMock()
    page.url = 'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LP72'
    frame = page.query_selector.return_value.content_frame.return_value
    frame.inner_text.return_value = '보유중인 예치금 충전 500 원'
    before_buy = MagicMock()

    with pytest.raises(RuntimeError, match='예치금 부족'):
        runner.purchase_tickets(page, before_buy=before_buy)

    before_buy.assert_not_called()
    assert not any(call.args == ('a.lotto720_btn_pay',) for call in frame.click.call_args_list)


def test_mobile_insufficient_deposit_stops_before_purchase_attempt(monkeypatch):
    from unittest.mock import MagicMock
    import pytest
    import pension720_runner as runner

    monkeypatch.setattr(runner.time, 'sleep', lambda seconds: None)
    page = MagicMock()
    page.url = 'https://el.dhlottery.co.kr/game_mobile/pension720/game.jsp'
    page.query_selector.return_value = None
    page.inner_text.return_value = '보유중인 예치금 충전 500 원'
    before_buy = MagicMock()

    with pytest.raises(RuntimeError, match='예치금 부족'):
        runner._purchase_mobile(page, before_buy=before_buy)

    before_buy.assert_not_called()
    assert not any(call.args == ('doOrder()',) for call in page.evaluate.call_args_list)
