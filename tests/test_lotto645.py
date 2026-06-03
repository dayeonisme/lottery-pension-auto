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
