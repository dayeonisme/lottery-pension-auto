#!/usr/bin/env python3
"""구매 페이지 디버그: iframe 로드 여부 및 팝업 상태 확인"""
import os
import time
from playwright.sync_api import sync_playwright

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
LOG = '/home/ubuntu/lottery_auto/logs/purchase_debug2.png'

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'],
    )
    page = browser.new_context(
        user_agent=UA,
        viewport={'width': 1280, 'height': 720},
        is_mobile=False,
    ).new_page()

    page.goto('https://www.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    page.fill('#inpUserId', os.environ['DHLOTTERY_ID'])
    page.fill('#inpUserPswdEncn', os.environ['DHLOTTERY_PW'])
    page.click('#btnLogin')
    page.wait_for_load_state('networkidle', timeout=30000)
    print('login url:', page.url)

    # 모바일 구매 URL 테스트
    page.goto(
        'https://el.dhlottery.co.kr/game_mobile/pension720/game.jsp',
        wait_until='domcontentloaded',
        timeout=30000,
    )
    time.sleep(3)

    print('purchase url:', page.url)
    print('iframe exists:', page.query_selector('iframe#ifrm_tab') is not None)

    info = page.evaluate("""() => {
        const iframe = document.querySelector('iframe#ifrm_tab');
        const popups = Array.from(document.querySelectorAll('*')).filter(el => {
            const s = window.getComputedStyle(el);
            const r = el.getBoundingClientRect();
            return s.display !== 'none' && s.visibility !== 'hidden'
                && r.width > 100 && r.height > 50
                && String(el.className).match(/popup|alert|layer|modal/i);
        }).map(el => el.innerText.trim().replace(/\\s+/g, ' ').substring(0, 200));
        return {
            iframe_src: iframe ? iframe.src : null,
            iframe_display: iframe ? window.getComputedStyle(iframe).display : null,
            popups: popups.filter(t => t.length > 5),
            body_text: document.body.innerText.substring(0, 500),
        };
    }""")
    print('iframe src:', info['iframe_src'])
    print('iframe display:', info['iframe_display'])
    print('popups:', info['popups'])
    print('body preview:', info['body_text'][:300])

    page.screenshot(path=LOG, full_page=True)
    print('screenshot saved:', LOG)
    browser.close()
