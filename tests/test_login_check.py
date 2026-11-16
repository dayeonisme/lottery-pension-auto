import sys
import os
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from login_check import wait_after_login_click


def test_never_waits_for_networkidle():
    page = MagicMock()
    wait_after_login_click(page)
    states = [c.args[0] for c in page.wait_for_load_state.call_args_list]
    assert 'networkidle' not in states
    assert states == ['domcontentloaded', 'load']
    page.wait_for_url.assert_called_once()


def test_load_timeout_is_not_fatal():
    # 2026-11-13: 메인 페이지 백그라운드 요청으로 대기 timeout → 예외 없이 진행해야 함
    page = MagicMock()

    def wait(state, timeout):
        if state == 'load':
            raise PlaywrightTimeoutError('Timeout 15000ms exceeded.')

    page.wait_for_load_state.side_effect = wait
    wait_after_login_click(page)  # no raise


def test_url_timeout_defers_to_ensure_logged_in():
    # 로그인 실패로 /login에 머무르면 여기선 넘기고 ensure_logged_in()이 판정
    page = MagicMock()
    page.wait_for_url.side_effect = PlaywrightTimeoutError('Timeout 30000ms exceeded.')
    wait_after_login_click(page)  # no raise
