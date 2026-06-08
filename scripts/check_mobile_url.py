#!/usr/bin/env python3
import os
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu'])
    page = browser.new_page()
    page.goto('https://www.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    page.fill('#inpUserId', os.environ['DHLOTTERY_ID'])
    page.fill('#inpUserPswdEncn', os.environ['DHLOTTERY_PW'])
    page.click('#btnLogin')
    page.wait_for_load_state('networkidle', timeout=30000)
    page.goto('https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40', wait_until='networkidle', timeout=30000)
    # m.dhlottery.co.kr 로그인 시도
    page.goto('https://m.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    print('m login URL:', page.url)
    inputs = page.evaluate("() => Array.from(document.querySelectorAll('input')).map(e=>({id:e.id,name:e.name,type:e.type}))")
    print('inputs:', inputs)
    if page.query_selector('#inpUserId') or page.query_selector('input[name*=id]'):
        id_sel = '#inpUserId' if page.query_selector('#inpUserId') else 'input[name*=id]'
        pw_sel = '#inpUserPswdEncn' if page.query_selector('#inpUserPswdEncn') else 'input[type=password]'
        page.fill(id_sel, os.environ['DHLOTTERY_ID'])
        page.fill(pw_sel, os.environ['DHLOTTERY_PW'])
        page.click('button[type=submit], #btnLogin, .btn_login', timeout=5000)
        page.wait_for_load_state('networkidle', timeout=15000)
        print('After m-login URL:', page.url)

    # m.dhlottery.co.kr 모바일 메인에서 로또6/45 구매 버튼 탐색
    page.goto('https://m.dhlottery.co.kr/', wait_until='networkidle', timeout=30000)
    print('Mobile main URL:', page.url)
    # onclick 포함 모든 링크/버튼
    items = page.evaluate("""() => Array.from(document.querySelectorAll('a,button')).map(e => ({
        tag: e.tagName,
        text: e.innerText.trim().slice(0,40),
        href: e.getAttribute('href') || '',
        onclick: e.getAttribute('onclick') || '',
        id: e.id,
    })).filter(e => e.text.includes('로또') || e.onclick || e.href.includes('lotto') || e.href.includes('645'))""")
    for i in items:
        print(i)

    # 로그인 상태 확인
    login_state = page.evaluate("() => document.querySelector('.logout-btn, #gnb_logout, a[href*=\"logout\"]')?.innerText || 'not found'")
    print('Login indicator:', login_state)
    member_info = page.evaluate("() => document.querySelector('.member-info, .user-name, .login-info')?.innerText || 'not found'")
    print('Member info:', member_info)

    # ol.dhlottery.co.kr 메인 방문 (로그인 상태 확인)
    page.goto('https://ol.dhlottery.co.kr/', wait_until='domcontentloaded', timeout=20000)
    print('ol main URL:', page.url)

    # game645.do 접근
    page.goto('https://ol.dhlottery.co.kr/olotto/game_mobile/game645.do', wait_until='networkidle', timeout=30000)
    print('game645 URL:', page.url)
    print('Title:', page.title())
    print('Body:', page.inner_text('body')[:600])
    browser.close()
