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
