"""
login_check.py
로그인 클릭 후 실제 로그인 성립 확인.
- 비밀번호 장기 미변경 계정은 /mbrsrvc/ExpryPswdNoti(비밀번호 변경안내)로 이동하며, 이 페이지에선
  세션이 아직 미성립("로그인을 해주세요") → 구매 페이지가 빈 화면/doVerify 무응답 (2026-10-16 연금 실패).
  "다음에 변경"(30일 연장)을 눌러 통과. 30일마다 다시 뜸.
- URL에 /login이 없다는 것만으로는 판정 불가 → 로그인 시에만 보이는 #logoutBtn으로 확인.
"""

import logging

PSWD_NOTICE_PATH = '/mbrsrvc/ExpryPswdNoti'


def ensure_logged_in(page) -> None:
    from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
    if PSWD_NOTICE_PATH in page.url:
        logging.warning('Password change notice after login — clicking "다음에 변경" (30-day deferral)')
        page.get_by_text('다음에 변경', exact=True).first.click()
        try:
            page.wait_for_url(lambda u: PSWD_NOTICE_PATH not in u, timeout=15000)
        except PlaywrightTimeoutError:
            pass  # 아래 #logoutBtn 확인에서 최종 판정
    try:
        page.wait_for_selector('#logoutBtn', state='visible', timeout=15000)
    except PlaywrightTimeoutError:
        raise RuntimeError(
            f'Login failed: #logoutBtn not visible after login (url={page.url}) '
            '— check DHLOTTERY_ID/PW, CAPTCHA, or a new post-login notice page'
        ) from None
