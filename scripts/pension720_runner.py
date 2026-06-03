#!/usr/bin/env python3
"""
pension720_runner.py
Pension Lottery 720+ automation: fetch results → check prizes → purchase → update Sheets
Exit 0 on success, 1 on failure.
"""

import sys
import os
import json
import time
import signal
import logging
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).parent.parent
PURCHASES_PATH = ROOT / 'data' / 'pension720_purchases.json'
LAST_RUN_PATH = ROOT / 'data' / 'last_run.json'
LOG_PATH = ROOT / 'logs' / 'pension720.log'
LOCK_PATH = ROOT / 'data' / 'pension720.lock'

sys.path.insert(0, str(Path(__file__).parent))
from google_sheets import update_prize_results, append_purchase_rows

USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36'
KST = timezone(timedelta(hours=9))

DEFAULT_LAST_RUN = {
    'lotto645': {
        'last_run': None, 'last_success': None, 'last_round': 0,
        'pending_sheets_round': 0, 'status': 'never', 'last_error': None,
    },
    'pension720': {
        'last_run': None, 'last_success': None, 'last_round': 0,
        'pending_sheets_round': 0, 'status': 'never', 'last_error': None,
    },
}


def send_telegram(message: str):
    token = os.environ.get('TELEGRAM_BOT_TOKEN', '')
    chat_id = os.environ.get('TELEGRAM_CHAT_ID', '')
    if not token or not chat_id:
        logging.warning('Telegram credentials not set, skipping notification')
        return
    try:
        url = f'https://api.telegram.org/bot{token}/sendMessage'
        data = json.dumps({'chat_id': chat_id, 'text': message}).encode()
        req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
        urllib.request.urlopen(req, timeout=10)
    except Exception as e:
        logging.warning('Telegram notification failed: %s', e)


def now_kst() -> datetime:
    return datetime.now(KST)


def next_thursday() -> str:
    d = now_kst()
    days_ahead = (3 - d.weekday()) % 7 or 7  # 3=목요일, or 7: 오늘이 목요일이면 다음 주
    return (d + timedelta(days=days_ahead)).strftime('%Y-%m-%d')


def check_prize(ticket_group: int, ticket_numbers: str, win_group: int, win_numbers: str, bonus_numbers: str = '') -> dict:
    group_match = ticket_group == win_group
    if group_match and ticket_numbers == win_numbers: return {'rank': '1st', 'prize': 0}
    if not group_match and ticket_numbers == win_numbers: return {'rank': '2nd', 'prize': 0}
    if bonus_numbers and ticket_numbers == bonus_numbers: return {'rank': 'bonus', 'prize': 0}
    if ticket_numbers[-5:] == win_numbers[-5:]: return {'rank': '3rd', 'prize': 1000000}
    if ticket_numbers[-4:] == win_numbers[-4:]: return {'rank': '4th', 'prize': 100000}
    if ticket_numbers[-3:] == win_numbers[-3:]: return {'rank': '5th', 'prize': 50000}
    if ticket_numbers[-2:] == win_numbers[-2:]: return {'rank': '6th', 'prize': 5000}
    if ticket_numbers[-1:] == win_numbers[-1:]: return {'rank': '7th', 'prize': 1000}
    return {'rank': 'no prize', 'prize': 0}


def _init_last_run():
    LAST_RUN_PATH.write_text(json.dumps(DEFAULT_LAST_RUN, indent=2, ensure_ascii=False))


def _read_last_run() -> dict:
    return json.loads(LAST_RUN_PATH.read_text(encoding='utf-8'))


def _write_last_run(data: dict):
    LAST_RUN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def update_last_run(status: str, round_no: int = 0, error: str = None):
    data = _read_last_run()
    data['pension720']['last_run'] = now_kst().isoformat()
    data['pension720']['status'] = status
    if round_no:
        data['pension720']['last_round'] = round_no
    if status == 'success':
        data['pension720']['last_success'] = now_kst().isoformat()
        data['pension720']['last_error'] = None
    if error:
        data['pension720']['last_error'] = error
    _write_last_run(data)


def set_pending_sheets_round(round_no: int):
    data = _read_last_run()
    data['pension720']['pending_sheets_round'] = round_no
    _write_last_run(data)


# STEP 1: 최신 당첨번호 조회
def fetch_winning_numbers(page) -> dict:
    page.goto('https://www.dhlottery.co.kr/pt720/result', wait_until='networkidle', timeout=30000)

    result = page.evaluate("""() => {
        const wraps = document.querySelectorAll('.result-infoWrap');
        const wrap = wraps[wraps.length - 1];

        const roundText = wrap?.querySelector('.result-txt')?.textContent || '';
        const round = parseInt((roundText.match(/\\d+/) || ['0'])[0]);

        const dateText = wrap?.querySelector('.result-date')?.textContent || '';
        const dm = dateText.match(/(\\d{4})\\.(\\d{2})\\.(\\d{2})/);
        const drawDate = dm ? `${dm[1]}-${dm[2]}-${dm[3]}` : '';

        const balls = wrap?.querySelectorAll('.result-wfBall');
        const firstBall = balls?.[0];
        const bonusBall = balls?.[1];

        const winGroup = parseInt(firstBall?.querySelector('.pension-jo')?.textContent?.trim() || '0');

        const digits = [1,2,3,4,5,6].map(i =>
            firstBall?.querySelector(`.wf-${i}n`)?.textContent?.trim() || ''
        );
        const winNumbers = digits.join('');

        const bonusDigits = [1,2,3,4,5,6].map(i =>
            bonusBall?.querySelector(`.wf-${i}n`)?.textContent?.trim() || ''
        );
        const bonusNumbers = bonusDigits.join('');

        return { round, winGroup, winNumbers, bonusNumbers, drawDate };
    }""")

    if not result['round'] or not result['winGroup'] or len(result['winNumbers']) != 6 or not result['winNumbers'].isdigit():
        raise RuntimeError(f"Failed to fetch pension winning numbers. Got: {result}")
    if len(result.get('bonusNumbers', '')) != 6 or not result['bonusNumbers'].isdigit():
        logging.warning('Bonus numbers missing or invalid: %s', result.get('bonusNumbers'))
        result['bonusNumbers'] = ''
    return result


# STEP 2: 지난 회차 당첨 확인 (동일 회차 복수 구매 세션 모두 처리)
def check_prizes(win_info: dict, dry_run: bool = False) -> list:
    """미확인 항목 전체 처리. 반환: [{purchase_date, round, ticket_results}, ...]"""
    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    entries = [e for e in data['pension720']
               if not e['result']['checked'] and e['round'] == win_info['round']]
    if not entries:
        logging.info('No unchecked entries for round %d, skipping prize check.', win_info['round'])
        return []

    all_results = []
    for entry in entries:
        ticket_results = []
        for ticket in entry['tickets']:
            r = check_prize(ticket['group'], ticket['numbers'], win_info['winGroup'], win_info['winNumbers'], win_info.get('bonusNumbers', ''))
            ticket_results.append({'no': ticket['no'], 'rank': r['rank'], 'prize': r['prize']})
        total = sum(t['prize'] for t in ticket_results)
        logging.info('Prize check round %d (%s): %d KRW', entry['round'], entry['purchase_date'], total)

        if not dry_run:
            entry['result'] = {
                'winning_group': win_info['winGroup'],
                'winning_numbers': win_info['winNumbers'],
                'checked': True,
                'tickets': ticket_results,
                'total_prize': total,
            }
        all_results.append({
            'purchase_date': entry['purchase_date'],
            'round': entry['round'],
            'ticket_results': ticket_results,
        })

    if not dry_run:
        PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        set_pending_sheets_round(win_info['round'])

    return all_results


# STEP 3 모바일 플로우 (GCP IP 차단 우회: el.dhlottery.co.kr/game_mobile/)
def _purchase_mobile(page) -> list:
    """전제: 이미 로그인된 page. 모바일 전용 구매 페이지 사용."""
    page.goto(
        'https://el.dhlottery.co.kr/game_mobile/pension720/game.jsp',
        wait_until='networkidle', timeout=30000,
    )
    logging.info('Mobile purchase page: %s', page.url)
    if 'login' in page.url or page.query_selector('#inpUserId') is not None:
        raise RuntimeError(f'Mobile purchase: session not carried over, redirected to login. URL: {page.url}')

    # 조별로 popup4 열기 → 조 선택 → 자동번호 → 선택완료 (doVerify 후 popup 자동 닫힘)
    for jo in range(1, 6):
        page.evaluate('selNumberPopup()')  # 매 조마다 popup4 열기
        time.sleep(0.5)
        page.click(f'label[for="group_sel{jo}"]')  # radio input은 hidden → label 클릭
        time.sleep(0.3)
        page.evaluate('doAuto()')
        time.sleep(0.8)
        page.evaluate('doVerify()')
        time.sleep(1.5)  # AJAX 완료 대기 (e2-micro)
        logging.info('%d조 번호 선택 완료', jo)

    logging.info('번호 선택 완료 — 구매 진행')
    page.evaluate('doOrder()')  # confirm 다이얼로그는 page.on('dialog') 에서 자동 수락

    page.wait_for_selector('.buyComplete', state='visible', timeout=15000)

    tickets = page.evaluate("""() => {
        return Array.from(document.querySelectorAll('.saleTicket li')).map((li, idx) => {
            const groupEl = li.querySelector('.lotto720_popup_group');
            if (!groupEl) return null;
            const group = parseInt(groupEl.innerText);
            const m = li.innerText.match(/\\d{6}/);
            const numbers = m ? m[0] : '';
            return { no: idx + 1, group, numbers, type: 'auto' };
        }).filter(t => t && t.group > 0 && t.numbers.length === 6);
    }""")

    if not tickets or len(tickets) != 5:
        raise RuntimeError(f'Mobile purchase: could not extract 5 tickets (got {len(tickets) if tickets else 0})')

    logging.info('Purchased %d tickets (mobile flow)', len(tickets))
    return tickets


# STEP 3: 5게임 자동구매 — 데스크탑 우선, 모바일 폴백
def purchase_tickets(page) -> list:
    page.on('dialog', lambda d: d.accept())

    logging.info('Navigating to login page...')
    page.goto('https://www.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    page.wait_for_selector('#inpUserId', timeout=10000)
    page.fill('#inpUserId', os.environ['DHLOTTERY_ID'])
    page.fill('#inpUserPswdEncn', os.environ['DHLOTTERY_PW'])
    page.click('#btnLogin')
    page.wait_for_load_state('networkidle', timeout=30000)

    is_logged_in = '/login' not in page.url
    if not is_logged_in:
        raise RuntimeError('Login failed: check DHLOTTERY_ID/PW or CAPTCHA')
    logging.info('Login successful')

    # 데스크탑 구매 페이지 시도
    page.goto(
        'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LP72',
        wait_until='networkidle', timeout=30000
    )

    # 모바일로 리다이렉트됐으면 모바일 플로우로 전환
    if 'm.dhlottery.co.kr' in page.url:
        logging.info('Desktop purchase page redirected to mobile — switching to mobile flow')
        return _purchase_mobile(page)

    # 팝업(미수령 당첨금 안내 등) 닫기 시도
    try:
        popup = page.wait_for_selector('.popup_section a[href*="receipt"], .popup_close, .btn_close', timeout=3000)
        if popup:
            popup.click()
            time.sleep(0.5)
    except Exception:
        pass

    # iframe 로드 완료까지 대기 (e2-micro 대응: 30초)
    page.wait_for_selector('iframe#ifrm_tab', timeout=30000)
    frame_el = page.query_selector('iframe#ifrm_tab')
    frame = frame_el.content_frame()
    if frame is None:
        raise RuntimeError('iframe#ifrm_tab content_frame() returned None')

    frame.wait_for_selector('a.lotto720_btn_auto_number', timeout=10000)

    # 조별로 다른 자동번호 선택: span.jogroup.num{N} → 자동번호 → 선택완료 반복
    for jo in range(1, 6):
        frame.click(f'span.jogroup.num{jo}')
        time.sleep(0.3)
        frame.click('a.lotto720_btn_auto_number')
        time.sleep(0.8)
        frame.click('a.lotto720_btn_confirm_number')
        time.sleep(0.3)
        logging.info('%d조 번호 선택 완료', jo)

    logging.info('번호 선택 완료 — 구매 진행')

    # 구매하기 클릭 → 확인 팝업에서 최종 구매 확정
    frame.click('a.lotto720_btn_pay')
    frame.wait_for_selector('#lotto720_popup_confirm', state='visible', timeout=10000)
    frame.click('#lotto720_popup_confirm a.btn_blue')  # doOrderRequest()
    frame.wait_for_selector('#lotto720_popup_pay', state='visible', timeout=15000)

    # 구매 완료 확인 후 티켓 추출
    tickets = frame.evaluate("""() => {
        return Array.from(document.querySelectorAll('.saleTicket li')).map((li, idx) => {
            const groupEl = li.querySelector('.lotto720_popup_group');
            if (!groupEl) return null;
            const group = parseInt(groupEl.innerText);
            const m = li.innerText.match(/\\d{6}/);
            const numbers = m ? m[0] : '';
            return { no: idx + 1, group, numbers, type: 'auto' };
        }).filter(t => t && t.group > 0 && t.numbers.length === 6);
    }""")

    if not tickets or len(tickets) != 5:
        raise RuntimeError(f'Purchase succeeded but could not extract 5 tickets (got {len(tickets) if tickets else 0})')

    logging.info('Purchased %d tickets', len(tickets))
    return tickets


# STEP 4: purchases.json 저장 + Sheets 업데이트
def save_and_update_sheets(win_round: int, tickets: list, prize_results: list, draw_date: str):
    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    new_round = win_round + 1
    purchase_date = now_kst().strftime('%Y-%m-%d %H:%M:%S')

    new_entry = {
        'round': new_round,
        'purchase_date': purchase_date,
        'draw_date': draw_date,
        'tickets': tickets,
        'result': {
            'winning_group': 0, 'winning_numbers': '',
            'checked': False, 'tickets': [],
        },
    }
    data['pension720'].append(new_entry)
    PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if prize_results:
        total_updated = 0
        for pr in prize_results:
            updated = update_prize_results('pension720', pr['round'], pr['ticket_results'], pr['purchase_date'])
            logging.info('Sheets: updated %d prize rows for round %d (%s)', updated, pr['round'], pr['purchase_date'])
            if updated == 0:
                logging.warning('Sheets: 0 rows matched for %s round %d — purchase_date mismatch?', pr['purchase_date'], pr['round'])
            total_updated += updated
        if total_updated > 0:
            set_pending_sheets_round(0)
        else:
            logging.warning('Sheets: prize update wrote 0 rows total — pending_sheets_round kept for retry')

    append_purchase_rows('pension720', new_entry)
    logging.info('Sheets: appended 5 rows for round %d', new_round)


def _run_timeout(signum, frame):
    print('[pension720] 600s timeout — force exit', file=sys.stderr, flush=True)
    os._exit(1)


def main():
    dry_run = '--dry-run' in sys.argv
    test_sheets = '--test-sheets' in sys.argv

    (ROOT / 'logs').mkdir(exist_ok=True)
    (ROOT / 'data').mkdir(exist_ok=True)
    if not PURCHASES_PATH.exists():
        PURCHASES_PATH.write_text(json.dumps({'pension720': []}, indent=2, ensure_ascii=False))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
        ],
    )

    signal.signal(signal.SIGALRM, _run_timeout)
    signal.alarm(600)

    # --test-sheets: 브라우저/구매 없이 STEP 4만 실행 (더미 데이터)
    if test_sheets:
        logging.info('=== pension720 STEP 4 test ===')
        dummy_round = 9999
        dummy_tickets = [{'no': 1, 'group': 1, 'numbers': '000001', 'type': 'auto'}]
        dummy_entry = {
            'round': dummy_round,
            'purchase_date': now_kst().strftime('%Y-%m-%d %H:%M:%S'),
            'draw_date': next_thursday(),
            'tickets': dummy_tickets,
            'result': {'winning_group': 0, 'winning_numbers': '', 'checked': False, 'tickets': []},
        }
        logging.info('STEP 4: Updating Google Sheets with dummy data (round %d)...', dummy_round)
        append_purchase_rows('pension720', dummy_entry)
        logging.info('STEP 4 test complete')
        return

    logging.info('=== pension720 automation start ===')

    # dry-run 시 lock 파일 생성/삭제 건너뜀 (스펙: "파일 수정 없음")
    if not dry_run:
        if LOCK_PATH.exists():
            try:
                pid = int(LOCK_PATH.read_text())
                os.kill(pid, 0)
                print(f'Already running (PID {pid}). Exiting.', file=sys.stderr)
                sys.exit(1)
            except (ValueError, ProcessLookupError, PermissionError):
                pass  # stale lock — 무시하고 진행
        LOCK_PATH.write_text(str(os.getpid()))

    try:
        if not LAST_RUN_PATH.exists():
            _init_last_run()

        if not dry_run:
            if not os.environ.get('DHLOTTERY_ID') or not os.environ.get('DHLOTTERY_PW'):
                raise RuntimeError('DHLOTTERY_ID or DHLOTTERY_PW is not set')

            # pending_sheets_round 재시도
            pending_round = _read_last_run()['pension720'].get('pending_sheets_round', 0)
            if pending_round > 0:
                logging.info('Retrying Sheets update for round %d (pending)', pending_round)
                purchases = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
                checked_entries = [e for e in purchases['pension720']
                                   if e['round'] == pending_round and e['result']['checked']]
                total_retry = 0
                for e in checked_entries:
                    updated = update_prize_results('pension720', pending_round, e['result']['tickets'], e['purchase_date'])
                    logging.info('Sheets retry: %d rows for round %d (%s)', updated, pending_round, e['purchase_date'])
                    if updated == 0:
                        logging.warning('Sheets retry: 0 rows matched for %s — purchase_date mismatch?', e['purchase_date'])
                    total_retry += updated
                if total_retry > 0:
                    set_pending_sheets_round(0)
                elif checked_entries:
                    logging.warning('Sheets retry: 0 rows total — pending_sheets_round kept for next run')
                else:
                    logging.warning('Sheets retry: no checked entries for round %d — clearing stale pending flag', pending_round)
                    set_pending_sheets_round(0)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-software-rasterizer',
                    '--disable-extensions',
                ]
            )
            try:
                context = browser.new_context(
                    user_agent=USER_AGENT,
                    viewport={'width': 1280, 'height': 720},
                    is_mobile=False,
                )
                page = context.new_page()

                logging.info('STEP 1: Fetching winning numbers...')
                win_info = fetch_winning_numbers(page)
                logging.info('Round %d | Group: %d | Numbers: %s', win_info['round'], win_info['winGroup'], win_info['winNumbers'])

                logging.info('STEP 2: Checking prizes...')
                prize_results = check_prizes(win_info, dry_run=dry_run)

                if not dry_run:
                    draw_date = next_thursday()
                    logging.info('STEP 3: Purchasing tickets...')
                    tickets = purchase_tickets(page)

                    logging.info('STEP 4: Updating Google Sheets...')
                    save_and_update_sheets(win_info['round'], tickets, prize_results, draw_date)

                    update_last_run('success', win_info['round'])
                    logging.info('=== pension720 automation complete ===')
                    ticket_lines = '\n'.join(
                        f'  {t["group"]}조 {t["numbers"]}'
                        for t in tickets
                    )
                    prize_alert = ''
                    if prize_results:
                        top_ranks = [t for pr in prize_results for t in pr['ticket_results'] if t['rank'] in ('1st', '2nd')]
                        if top_ranks:
                            prize_alert = f'\n\n⚠️ {prize_results[0]["round"]}회 {top_ranks[0]["rank"]} 당첨! 수동 확인 필요'
                            logging.warning('HIGH RANK WIN: round=%d rank=%s — manual prize check required', prize_results[0]['round'], top_ranks[0]['rank'])
                    send_telegram(
                        f'[OK] 연금복권720+ 제{win_info["round"] + 1}회 구매 완료\n\n'
                        f'🎟 구매 번호:\n{ticket_lines}\n\n'
                        f'📅 추첨일: {draw_date}\n'
                        f'🕐 구매시각: {now_kst().strftime("%Y-%m-%d %H:%M")}'
                        f'{prize_alert}'
                    )
                else:
                    logging.info('[DRY-RUN] STEP 3+4 skipped. Prize results: %d entries', len(prize_results))
            finally:
                signal.alarm(0)
                browser.close()

    except Exception as e:
        import traceback
        logging.error('%s\n%s', repr(e), traceback.format_exc())
        if not dry_run:
            try:
                update_last_run('error', 0, str(e))
            except Exception:
                pass
            send_telegram(
                f'[FAIL] pension720 automation failed\n\n'
                f'Run time: {now_kst().strftime("%Y-%m-%d %H:%M")}\n\n'
                f'Error: {e}'
            )
        sys.exit(1)
    finally:
        if not dry_run:
            LOCK_PATH.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
