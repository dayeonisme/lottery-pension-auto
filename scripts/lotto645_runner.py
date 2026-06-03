#!/usr/bin/env python3
"""
lotto645_runner.py
Lotto 6/45 automation: fetch results → check prizes → purchase → update Sheets
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

ROOT = Path(__file__).parent.parent
PURCHASES_PATH = ROOT / 'data' / 'lotto645_purchases.json'
LAST_RUN_PATH = ROOT / 'data' / 'last_run.json'
LOG_PATH = ROOT / 'logs' / 'lotto645.log'
LOCK_PATH = ROOT / 'data' / 'lotto645.lock'

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


def next_saturday() -> str:
    d = now_kst()
    days_ahead = (5 - d.weekday()) % 7 or 7  # 5=토요일, or 7: 오늘이 토요일이면 다음 주
    return (d + timedelta(days=days_ahead)).strftime('%Y-%m-%d')


def check_prize(ticket_numbers: list, win_nums: list, bonus: int) -> dict:
    matched = [n for n in ticket_numbers if n in win_nums]
    count = len(matched)
    has_bonus = bonus in ticket_numbers
    if count == 6: return {'rank': '1st', 'prize': 0}
    if count == 5 and has_bonus: return {'rank': '2nd', 'prize': 0}
    if count == 5: return {'rank': '3rd', 'prize': 0}   # 변동 상금 — 수동 확인 필요
    if count == 4: return {'rank': '4th', 'prize': 50000}
    if count == 3: return {'rank': '5th', 'prize': 5000}
    return {'rank': 'no prize', 'prize': 0}


def _init_last_run():
    LAST_RUN_PATH.write_text(json.dumps(DEFAULT_LAST_RUN, indent=2, ensure_ascii=False))


def _read_last_run() -> dict:
    return json.loads(LAST_RUN_PATH.read_text(encoding='utf-8'))


def _write_last_run(data: dict):
    LAST_RUN_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))


def update_last_run(status: str, round_no: int = 0, error: str = None):
    data = _read_last_run()
    data['lotto645']['last_run'] = now_kst().isoformat()
    data['lotto645']['status'] = status
    if round_no:
        data['lotto645']['last_round'] = round_no
    if status == 'success':
        data['lotto645']['last_success'] = now_kst().isoformat()
        data['lotto645']['last_error'] = None
    if error:
        data['lotto645']['last_error'] = error
    _write_last_run(data)


def set_pending_sheets_round(round_no: int):
    data = _read_last_run()
    data['lotto645']['pending_sheets_round'] = round_no
    _write_last_run(data)


# STEP 1: 최신 당첨번호 조회 (브라우저 세션 내 fetch — IP 차단 우회)
def fetch_winning_numbers(page) -> dict:
    page.goto('https://www.dhlottery.co.kr/', wait_until='domcontentloaded', timeout=30000)

    result = page.evaluate("""() => {
        return fetch('/selectMainInfo.do', {
            headers: { 'Referer': 'https://www.dhlottery.co.kr/' }
        })
        .then(r => r.json())
        .then(data => {
            const arr = data?.data?.result?.pstLtEpstInfo?.lt645 || [];
            const lt = arr.reduce((max, x) => parseInt(x.ltEpsd) > parseInt(max.ltEpsd) ? x : max, arr[0]);
            if (!lt) return { round: 0, numbers: [], bonus: 0, drawDate: '' };
            const drawDateRaw = lt.ltRflYmd || '';
            const drawDate = drawDateRaw.length === 8
                ? drawDateRaw.slice(0,4) + '-' + drawDateRaw.slice(4,6) + '-' + drawDateRaw.slice(6)
                : drawDateRaw;
            return {
                round: parseInt(lt.ltEpsd),
                numbers: [1,2,3,4,5,6].map(i => parseInt(lt['tm' + i + 'WnNo'])),
                bonus: parseInt(lt.bnsWnNo),
                drawDate: drawDate,
            };
        })
        .catch(() => ({ round: 0, numbers: [], bonus: 0, drawDate: '' }));
    }""")

    if not result['round'] or len(result['numbers']) != 6:
        raise RuntimeError(f"Failed to fetch winning numbers. Got: {result}")
    return result


# STEP 2: 지난 회차 당첨 확인 (동일 회차 복수 구매 세션 모두 처리)
def check_prizes(win_info: dict, dry_run: bool = False) -> list:
    """미확인 항목 전체 처리. 반환: [{purchase_date, round, ticket_results}, ...]"""
    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    entries = [e for e in data['lotto645']
               if not e['result']['checked'] and e['round'] == win_info['round']]
    if not entries:
        logging.info('No unchecked entries for round %d, skipping prize check.', win_info['round'])
        return []

    all_results = []
    for entry in entries:
        ticket_results = []
        for ticket in entry['tickets']:
            r = check_prize(ticket['numbers'], win_info['numbers'], win_info['bonus'])
            ticket_results.append({
                'no': ticket['no'],
                'rank': r['rank'],
                'prize': r['prize'],
                'matched': [n for n in ticket['numbers'] if n in win_info['numbers']],
            })
        total = sum(t['prize'] for t in ticket_results)
        logging.info('Prize check round %d (%s): %d KRW', entry['round'], entry['purchase_date'], total)

        if not dry_run:
            entry['result'] = {
                'winning_numbers': win_info['numbers'],
                'bonus_number': win_info['bonus'],
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


def _purchase_mobile_lotto645(page, count: int = 5) -> list:
    """전제: 이미 로그인된 page. ol.dhlottery.co.kr 모바일 전용 구매 페이지 사용."""
    # www.dhlottery.co.kr 로그인 쿠키를 ol.dhlottery.co.kr 도메인에 복사
    ctx = page.context
    all_cookies = ctx.cookies()
    ol_cookies = [
        {k: v for k, v in {**c, 'domain': 'ol.dhlottery.co.kr'}.items() if k != 'url'}
        for c in all_cookies if 'dhlottery.co.kr' in c.get('domain', '')
    ]
    if ol_cookies:
        ctx.add_cookies(ol_cookies)
        logging.info('Copied %d cookies to ol.dhlottery.co.kr', len(ol_cookies))

    page.goto(
        'https://ol.dhlottery.co.kr/olotto/game_mobile/game645.do',
        wait_until='networkidle', timeout=30000,
    )
    logging.info('Mobile lotto645 page: %s', page.url)
    if 'ol.dhlottery.co.kr' not in page.url:
        raise RuntimeError(f'Mobile purchase: redirected away from ol.dhlottery.co.kr. URL: {page.url}')

    for i in range(count):
        page.evaluate('addRandomNum()')
        time.sleep(0.8)
        logging.info('addRandomNum() %d/%d', i + 1, count)

    time.sleep(0.5)
    page.click('#btnBuy')

    page.wait_for_selector('.btn-rec01.buttonOk', state='visible', timeout=10000)
    page.click('.btn-rec01.buttonOk')
    logging.info('Purchase confirm clicked')

    # offsetParent가 null이면 조상 중 display:none 있음 — visible이 될 때까지 대기
    page.wait_for_function(
        "() => { const btn = document.getElementById('closeReceipt'); return btn ? btn.offsetParent !== null : false; }",
        timeout=15000,
    )

    tickets = page.evaluate("""() => {
        const rows = document.querySelectorAll('.ticket-num-wrap');
        return Array.from(rows).map((row, idx) => {
            const nums = Array.from(row.children).map(child => {
                const t = child.textContent.trim();
                return parseInt(t.charAt(0) === '0' ? t.slice(1) : t);
            }).filter(n => !isNaN(n) && n > 0);
            return { no: idx + 1, numbers: nums, type: 'auto' };
        }).filter(t => t.numbers.length === 6);
    }""")

    if len(tickets) != count:
        raise RuntimeError(f'Expected {count} tickets but got {len(tickets)}')
    logging.info('Mobile purchased %d tickets', len(tickets))
    return tickets


# STEP 3: 자동구매 (count: 구매 장수, 기본 5)
def purchase_tickets(page, count: int = 5) -> list:
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

    page.goto(
        'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40',
        wait_until='networkidle', timeout=30000
    )

    if 'm.dhlottery.co.kr' in page.url:
        logging.info('Desktop purchase page redirected to mobile — switching to mobile flow')
        return _purchase_mobile_lotto645(page, count)

    # 팝업(미수령 당첨금 안내 등) 닫기 시도
    try:
        popup = page.wait_for_selector('.popup_section a[href*="receipt"], .popup_close, .btn_close', timeout=3000)
        if popup:
            popup.click()
            time.sleep(0.5)
    except Exception:
        pass

    # 버그1 수정: iframe 로드 완료까지 대기 후 접근 (e2-micro 대응: 30초)
    page.wait_for_selector('iframe#ifrm_tab', timeout=30000)
    frame_el = page.query_selector('iframe#ifrm_tab')
    frame = frame_el.content_frame()
    if frame is None:
        raise RuntimeError('iframe#ifrm_tab content_frame() returned None')

    frame.wait_for_selector('a#num2', timeout=10000)
    frame.evaluate("() => document.querySelector('a#num2').click()")
    time.sleep(1)

    frame.select_option('select#amoundApply', str(count))
    time.sleep(0.5)

    frame.click('#btnSelectNum')
    time.sleep(1)

    frame.click('#btnBuy')
    time.sleep(1.5)

    # 버그2 수정: 팝업 확인 버튼 못 찾으면 에러
    confirmed = frame.evaluate("""() => {
        if (typeof closepopupLayerConfirm === 'function') {
            closepopupLayerConfirm(true);
            return true;
        }
        const btn = document.querySelector('input[onclick*="closepopupLayerConfirm(true)"]');
        if (btn) { btn.click(); return true; }
        return false;
    }""")
    if not confirmed:
        raise RuntimeError('Purchase confirm popup not found: closepopupLayerConfirm unavailable')

    # iframe이 구매 완료 페이지로 재이동하므로 frame 참조를 다시 가져옴
    frame_el = page.query_selector('iframe#ifrm_tab')
    frame = frame_el.content_frame()
    if frame is None:
        raise RuntimeError('iframe#ifrm_tab content_frame() returned None after purchase')
    frame.wait_for_load_state('networkidle', timeout=15000)

    # 구매 실패 팝업 감지 (networkidle 후 — e2-micro 렌더링 완료 보장)
    popup_msg = frame.evaluate("""() => {
        const candidates = document.querySelectorAll(
            '.popup_section, [class*="alert"], [class*="layer"], [class*="modal"], [class*="popup"]'
        );
        for (const el of candidates) {
            const style = window.getComputedStyle(el);
            const rect = el.getBoundingClientRect();
            if (style.display !== 'none' && style.visibility !== 'hidden' && rect.width > 50 && rect.height > 50) {
                const text = el.innerText.trim().replace(/\\s+/g, ' ');
                if (text.length > 10 && !el.querySelector('iframe')) {
                    return text.substring(0, 300);
                }
            }
        }
        return null;
    }""")
    if popup_msg:
        raise RuntimeError(f'Purchase blocked — site popup: {popup_msg}')
    frame.wait_for_selector('#reportRow li', timeout=15000)

    tickets = frame.evaluate("""() => {
        const items = document.querySelectorAll('#reportRow li');
        return Array.from(items).map((li, idx) => {
            const nums = Array.from(li.querySelectorAll('.nums span'))
                .map(el => parseInt(el.textContent.trim())).filter(n => !isNaN(n));
            return { no: idx + 1, numbers: nums, type: 'auto' };
        }).filter(t => t.numbers.length === 6);
    }""")

    if len(tickets) != count:
        raise RuntimeError(f'Expected {count} tickets but got {len(tickets)}')
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
            'winning_numbers': [], 'bonus_number': 0,
            'checked': False, 'tickets': [],
        },
    }
    data['lotto645'].append(new_entry)
    PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if prize_results:
        total_updated = 0
        for pr in prize_results:
            updated = update_prize_results('lotto645', pr['round'], pr['ticket_results'], pr['purchase_date'])
            logging.info('Sheets: updated %d prize rows for round %d (%s)', updated, pr['round'], pr['purchase_date'])
            if updated == 0:
                logging.warning('Sheets: 0 rows matched for %s round %d — purchase_date mismatch?', pr['purchase_date'], pr['round'])
            total_updated += updated
        if total_updated > 0:
            set_pending_sheets_round(0)
        else:
            logging.warning('Sheets: prize update wrote 0 rows total — pending_sheets_round kept for retry')

    append_purchase_rows('lotto645', new_entry)
    logging.info('Sheets: appended 5 rows for round %d', new_round)


def _run_timeout(signum, frame):
    print('[lotto645] 600s timeout — force exit', file=sys.stderr, flush=True)
    os._exit(1)


def main():
    dry_run = '--dry-run' in sys.argv
    test_sheets = '--test-sheets' in sys.argv

    count = 5
    if '--count' in sys.argv:
        idx = sys.argv.index('--count')
        count = int(sys.argv[idx + 1])
    elif '--test' in sys.argv:
        count = 1

    (ROOT / 'logs').mkdir(exist_ok=True)
    (ROOT / 'data').mkdir(exist_ok=True)
    if not PURCHASES_PATH.exists():
        PURCHASES_PATH.write_text(json.dumps({'lotto645': []}, indent=2, ensure_ascii=False))

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
        logging.info('=== lotto645 STEP 4 test ===')
        dummy_round = 9999
        dummy_tickets = [{'no': 1, 'numbers': [1, 2, 3, 4, 5, 6], 'type': 'auto'}]
        dummy_entry = {
            'round': dummy_round,
            'purchase_date': now_kst().strftime('%Y-%m-%d %H:%M:%S'),
            'draw_date': next_saturday(),
            'tickets': dummy_tickets,
            'result': {'winning_numbers': [], 'bonus_number': 0, 'checked': False, 'tickets': []},
        }
        logging.info('STEP 4: Updating Google Sheets with dummy data (round %d)...', dummy_round)
        append_purchase_rows('lotto645', dummy_entry)
        logging.info('STEP 4 test complete')
        return

    logging.info('=== lotto645 automation start ===')

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
            pending_round = _read_last_run()['lotto645'].get('pending_sheets_round', 0)
            if pending_round > 0:
                logging.info('Retrying Sheets update for round %d (pending)', pending_round)
                purchases = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
                checked_entries = [e for e in purchases['lotto645']
                                   if e['round'] == pending_round and e['result']['checked']]
                total_retry = 0
                for e in checked_entries:
                    updated = update_prize_results('lotto645', pending_round, e['result']['tickets'], e['purchase_date'])
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
                logging.info('Round %d | %s | Bonus: %d', win_info['round'], win_info['numbers'], win_info['bonus'])

                logging.info('STEP 2: Checking prizes...')
                prize_results = check_prizes(win_info, dry_run=dry_run)

                if not dry_run:
                    draw_date = next_saturday()
                    logging.info('STEP 3: Purchasing tickets (%d장)...', count)
                    tickets = purchase_tickets(page, count=count)

                    logging.info('STEP 4: Updating Google Sheets...')
                    save_and_update_sheets(win_info['round'], tickets, prize_results, draw_date)

                    update_last_run('success', win_info['round'])
                    logging.info('=== lotto645 automation complete ===')
                    ticket_lines = '\n'.join(
                        f'  {t["no"]}. {" ".join(str(n).zfill(2) for n in t["numbers"])}'
                        for t in tickets
                    )
                    prize_alert = ''
                    if prize_results:
                        top_ranks = [t for pr in prize_results for t in pr['ticket_results'] if t['rank'] in ('1st', '2nd', '3rd')]
                        if top_ranks:
                            prize_alert = f'\n\n⚠️ {prize_results[0]["round"]}회 {top_ranks[0]["rank"]} 당첨! 수동 확인 필요'
                            logging.warning('HIGH RANK WIN: round=%d rank=%s — manual prize check required', prize_results[0]['round'], top_ranks[0]['rank'])
                    send_telegram(
                        f'[OK] 로또6/45 제{win_info["round"] + 1}회 구매 완료\n\n'
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
                f'[FAIL] lotto645 automation failed\n\n'
                f'Run time: {now_kst().strftime("%Y-%m-%d %H:%M")}\n\n'
                f'Error: {e}'
            )
        sys.exit(1)
    finally:
        if not dry_run:
            LOCK_PATH.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
