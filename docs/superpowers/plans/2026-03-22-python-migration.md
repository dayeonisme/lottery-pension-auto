# Python Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Node.js 자동화 코드를 Python(Playwright sync + gspread + 서비스 계정)으로 완전히 교체한다.

**Architecture:** 기존 JS 4단계 흐름(당첨번호 조회 → 당첨 확인 → 구매 → Sheets 업데이트)을 그대로 유지하면서 언어만 교체한다. `google_sheets.py`는 두 러너가 공유하는 Sheets 헬퍼이고, 각 러너는 독립 실행 가능한 스크립트다.

**Tech Stack:** Python 3.12, playwright (sync API), gspread 6.x, google-auth, pytest

---

## 사전 조건 (코드 작성 전 수동 완료 필요)

- [ ] Google Cloud Console → 서비스 계정 생성 → JSON 키 다운로드 → `config/service_account.json` 저장
- [ ] 스프레드시트에 서비스 계정 이메일 **편집자**로 공유

---

## 파일 맵

| 경로 | 역할 |
|------|------|
| `requirements.txt` | 신규 생성 |
| `scripts/google_sheets.py` | 신규 생성 — Sheets 헬퍼 |
| `scripts/lotto645_runner.py` | 신규 생성 — Lotto 6/45 러너 |
| `scripts/pension720_runner.py` | 신규 생성 — Pension 720+ 러너 |
| `scripts/test_runner.py` | 신규 생성 — n8n 파이프라인 스모크 테스트 |
| `tests/__init__.py` | 신규 생성 |
| `tests/test_lotto645.py` | 신규 생성 — lotto645 단위 테스트 |
| `tests/test_pension720.py` | 신규 생성 — pension720 단위 테스트 |
| `.gitignore` | 수정 — `config/service_account.json` 추가 |
| `CLAUDE.md` | 수정 — Python 실행 명령어 추가 |

---

## Task 1: 프로젝트 셋업

**Files:**
- Create: `requirements.txt`
- Create: `tests/__init__.py`
- Modify: `.gitignore`

- [ ] **Step 1: requirements.txt 작성**

```
playwright
gspread
google-auth
pytest
```

- [ ] **Step 2: 패키지 설치**

```bash
pip install -r requirements.txt
playwright install chromium
```

Expected: 에러 없이 완료. `playwright --version` 으로 확인.

- [ ] **Step 3: tests 디렉터리 초기화**

`tests/__init__.py` 파일을 빈 파일로 생성.

- [ ] **Step 4: .gitignore에 서비스 계정 추가**

`.gitignore` 파일에서 아래 라인 추가(없으면):
```
config/service_account.json
```

- [ ] **Step 5: 커밋**

```bash
git add requirements.txt tests/__init__.py .gitignore
git commit -m "chore: Python 마이그레이션 프로젝트 셋업"
```

---

## Task 2: google_sheets.py

**Files:**
- Create: `scripts/google_sheets.py`

- [ ] **Step 1: google_sheets.py 작성**

```python
"""
google_sheets.py
Google Sheets helper using service account auth (gspread 6.x).
"""

import re
from datetime import datetime, timezone, timedelta
from pathlib import Path

from google.oauth2.service_account import Credentials
import gspread

ROOT = Path(__file__).parent.parent
SERVICE_ACCOUNT_PATH = ROOT / 'config' / 'service_account.json'
SPREADSHEET_ID = '<google-spreadsheet-id>'
SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive',
]

# Google Sheets A열 값 — 기존 데이터와 반드시 일치
LOTTERY_DISPLAY_NAME = {
    'lotto645': '로또6/45',
    'pension720': '연금복권720+',
}

KST = timezone(timedelta(hours=9))


def _now_kst_str() -> str:
    return datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')


def _today_kst() -> str:
    return datetime.now(KST).strftime('%Y-%m-%d')


def get_client() -> gspread.Client:
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return gspread.Client(auth=creds)


def update_prize_results(lottery_type: str, round_no: int, ticket_results: list) -> int:
    """raw 시트에서 lottery_type + round_no 행을 찾아 H~K 열 업데이트. 반환: 업데이트된 행 수."""
    client = get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet('raw')

    all_values = ws.get_all_values()
    display_name = LOTTERY_DISPLAY_NAME.get(lottery_type, lottery_type)
    today = _today_kst()

    updates = []
    for i, row in enumerate(all_values[1:], start=2):  # 1행은 헤더, 시트 행은 2부터
        if len(row) < 4:
            continue
        if row[0] == display_name and str(row[2]) == str(round_no):
            ticket_no = int(row[3]) if row[3].isdigit() else 0
            t = next((t for t in ticket_results if t['no'] == ticket_no), None)
            if not t:
                continue
            result_val = 'no prize' if t['rank'] == 'no prize' else 'win'
            rank_val = '-' if t['rank'] == 'no prize' else re.sub(r'(\d+)(st|nd|rd|th)', r'\1등', t['rank'])
            prize_val = str(t['prize']) if t['prize'] > 0 else '-'
            updates.append({
                'range': f'raw!H{i}:K{i}',
                'values': [[result_val, rank_val, prize_val, today]],
            })

    if updates:
        ws.spreadsheet.values_batch_update({
            'valueInputOption': 'RAW',
            'data': updates,
        })

    return len(updates)


def append_purchase_rows(lottery_type: str, purchase_data: dict) -> None:
    """raw 시트 하단에 티켓 1장당 1행씩 추가."""
    client = get_client()
    sh = client.open_by_key(SPREADSHEET_ID)
    ws = sh.worksheet('raw')

    display_name = LOTTERY_DISPLAY_NAME.get(lottery_type, lottery_type)
    now_str = _now_kst_str()

    rows = []
    for ticket in purchase_data['tickets']:
        if lottery_type == 'lotto645':
            numbers_str = ' '.join(str(n).zfill(2) for n in ticket['numbers'])
        else:
            numbers_str = f"{ticket['group']}-{ticket['numbers']}"
        rows.append([
            display_name, now_str, purchase_data['round'], ticket['no'],
            numbers_str, 1000, purchase_data['draw_date'],
            'pending', '-', '-', '-',
        ])

    ws.append_rows(rows, value_input_option='RAW')
```

- [ ] **Step 2: 연결 테스트**

> **주의:** 아래 명령은 프로젝트 루트(`lottery_auto/`)에서 실행해야 합니다.

```bash
python -c "
import sys
sys.path.insert(0, 'scripts')
from google_sheets import get_client, SPREADSHEET_ID
client = get_client()
sh = client.open_by_key(SPREADSHEET_ID)
print('시트 목록:', [ws.title for ws in sh.worksheets()])
"
```

Expected: `시트 목록: ['raw']` 출력. 오류 없음.

- [ ] **Step 3: 커밋**

```bash
git add scripts/google_sheets.py
git commit -m "feat: google_sheets.py — gspread 서비스 계정 인증"
```

---

## Task 3: lotto645 check_prize 단위 테스트 (TDD)

**Files:**
- Create: `tests/test_lotto645.py`
- Create: `scripts/lotto645_runner.py` (check_prize 함수만 먼저 작성)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_lotto645.py`:
```python
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

from lotto645_runner import check_prize


def test_1st_prize():
    assert check_prize([1, 2, 3, 4, 5, 6], [1, 2, 3, 4, 5, 6], 7) == {'rank': '1st', 'prize': 0}


def test_2nd_prize():
    assert check_prize([1, 2, 3, 4, 5, 7], [1, 2, 3, 4, 5, 6], 7) == {'rank': '2nd', 'prize': 0}


def test_3rd_prize():
    assert check_prize([1, 2, 3, 4, 5, 9], [1, 2, 3, 4, 5, 6], 7) == {'rank': '3rd', 'prize': 1500000}


def test_4th_prize():
    assert check_prize([1, 2, 3, 4, 9, 10], [1, 2, 3, 4, 5, 6], 7) == {'rank': '4th', 'prize': 50000}


def test_5th_prize():
    assert check_prize([1, 2, 3, 9, 10, 11], [1, 2, 3, 4, 5, 6], 7) == {'rank': '5th', 'prize': 5000}


def test_no_prize_two_match():
    assert check_prize([1, 2, 9, 10, 11, 12], [1, 2, 3, 4, 5, 6], 7) == {'rank': 'no prize', 'prize': 0}


def test_no_prize_zero_match():
    assert check_prize([10, 11, 12, 13, 14, 15], [1, 2, 3, 4, 5, 6], 7) == {'rank': 'no prize', 'prize': 0}
```

- [ ] **Step 2: check_prize만 포함한 스켈레톤 lotto645_runner.py 작성**

`scripts/lotto645_runner.py` (check_prize 함수만):
```python
def check_prize(ticket_numbers: list, win_nums: list, bonus: int) -> dict:
    matched = [n for n in ticket_numbers if n in win_nums]
    count = len(matched)
    has_bonus = bonus in ticket_numbers
    if count == 6: return {'rank': '1st', 'prize': 0}
    if count == 5 and has_bonus: return {'rank': '2nd', 'prize': 0}
    if count == 5: return {'rank': '3rd', 'prize': 1500000}
    if count == 4: return {'rank': '4th', 'prize': 50000}
    if count == 3: return {'rank': '5th', 'prize': 5000}
    return {'rank': 'no prize', 'prize': 0}
```

- [ ] **Step 3: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_lotto645.py -v
```

Expected: 7 passed

---

## Task 4: lotto645_runner.py 전체 구현

**Files:**
- Modify: `scripts/lotto645_runner.py` (전체 교체)

- [ ] **Step 1: 전체 lotto645_runner.py 작성**

```python
#!/usr/bin/env python3
"""
lotto645_runner.py
Lotto 6/45 automation: fetch results → check prizes → purchase → update Sheets
Exit 0 on success, 1 on failure (used by n8n IF node).
"""

import sys
import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHROME_PATH = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PURCHASES_PATH = ROOT / 'data' / 'lotto645_purchases.json'
LAST_RUN_PATH = ROOT / 'data' / 'last_run.json'
LOG_PATH = ROOT / 'logs' / 'lotto645.log'
LOCK_PATH = ROOT / 'data' / 'lotto645.lock'

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
    if count == 5: return {'rank': '3rd', 'prize': 1500000}
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
    if error:
        data['lotto645']['last_error'] = error
    _write_last_run(data)


def set_pending_sheets_round(round_no: int):
    data = _read_last_run()
    data['lotto645']['pending_sheets_round'] = round_no
    _write_last_run(data)


# STEP 1: 최신 당첨번호 조회
def fetch_winning_numbers(page) -> dict:
    page.goto('https://www.dhlottery.co.kr', wait_until='networkidle', timeout=30000)

    result = page.evaluate("""() => {
        const slide = document.querySelector(
            '.swiper-slide.lt645-inbox.swiper-slide-active, .lt645-inbox.swiper-slide-active'
        );
        if (!slide) return { round: 0, numbers: [], bonus: 0, drawDate: '' };

        const round = parseInt(
            (slide.querySelector('.lt645-round')?.textContent || '').replace(/[^0-9]/g, '')
        );

        const allBalls = Array.from(slide.querySelectorAll('.lt-ball'));
        const plusIdx = allBalls.findIndex(el => el.classList.contains('plus'));
        const numbers = allBalls
            .slice(0, plusIdx)
            .map(el => parseInt(el.textContent.trim()))
            .filter(n => !isNaN(n));
        const bonus = parseInt(allBalls[plusIdx + 1]?.textContent?.trim() || '0');

        const dateMatch = slide.textContent.match(/(\\d{4})[.\\-](\\d{1,2})[.\\-](\\d{1,2})/);
        const drawDate = dateMatch
            ? `${dateMatch[1]}-${dateMatch[2].padStart(2,'0')}-${dateMatch[3].padStart(2,'0')}`
            : '';

        return { round, numbers, bonus, drawDate };
    }""")

    if not result['round'] or len(result['numbers']) != 6:
        raise RuntimeError(f"Failed to fetch winning numbers. Got: {result}")
    return result


# STEP 2: 지난 회차 당첨 확인
def check_prizes(win_info: dict, dry_run: bool = False) -> dict | None:
    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    entry = next(
        (e for e in data['lotto645']
         if not e['result']['checked'] and e['round'] == win_info['round']),
        None
    )
    if not entry:
        logging.info('No unchecked entry for round %d, skipping prize check.', win_info['round'])
        return None

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
    logging.info('Prize check done for round %d. Total: %d KRW', entry['round'], total)

    if not dry_run:
        entry['result'] = {
            'winning_numbers': win_info['numbers'],
            'bonus_number': win_info['bonus'],
            'checked': True,
            'tickets': ticket_results,
            'total_prize': total,
        }
        PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        set_pending_sheets_round(entry['round'])

    return {'round': entry['round'], 'ticket_results': ticket_results}


# STEP 3: 5게임 자동구매
def purchase_tickets(page) -> list:
    page.on('dialog', lambda d: d.accept())

    logging.info('Navigating to login page...')
    page.goto('https://www.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    page.wait_for_selector('#inpUserId', timeout=10000)
    page.fill('#inpUserId', os.environ['DHLOTTERY_ID'])
    page.fill('#inpUserPswdEncn', os.environ['DHLOTTERY_PW'])
    page.click('#btnLogin')
    page.wait_for_load_state('networkidle', timeout=30000)

    is_logged_in = page.evaluate(
        "() => !!document.querySelector('#gnb_logout, .btn_logout, [href*=\"logout\"]')"
    )
    if not is_logged_in:
        raise RuntimeError('Login failed: check DHLOTTERY_ID/PW or CAPTCHA')
    logging.info('Login successful')

    page.goto(
        'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LO40',
        wait_until='networkidle', timeout=30000
    )

    frame_el = page.query_selector('iframe#ifrm_tab')
    frame = frame_el.content_frame() if frame_el else page.main_frame()

    frame.wait_for_selector('a#num2', timeout=10000)
    frame.evaluate("() => document.querySelector('a#num2').click()")
    time.sleep(1)

    frame.select_option('select#amoundApply', '5')
    time.sleep(0.5)

    frame.click('#btnSelectNum')
    time.sleep(1)

    frame.click('#btnBuy')
    time.sleep(1.5)

    frame.evaluate("""() => {
        if (typeof closepopupLayerConfirm === 'function') {
            closepopupLayerConfirm(true);
        } else {
            const btn = document.querySelector('input[onclick*="closepopupLayerConfirm(true)"]');
            if (btn) btn.click();
        }
    }""")

    frame.wait_for_selector('#reportRow li', timeout=15000)

    tickets = frame.evaluate("""() => {
        const items = document.querySelectorAll('#reportRow li');
        return Array.from(items).map((li, idx) => {
            const nums = Array.from(li.querySelectorAll('.nums span'))
                .map(el => parseInt(el.textContent.trim())).filter(n => !isNaN(n));
            return { no: idx + 1, numbers: nums, type: 'auto' };
        }).filter(t => t.numbers.length === 6);
    }""")

    if not tickets:
        raise RuntimeError('Could not extract purchased ticket numbers from receipt')
    logging.info('Purchased %d tickets', len(tickets))
    return tickets


# STEP 4: purchases.json 저장 + Sheets 업데이트
def save_and_update_sheets(win_round: int, tickets: list, prize_result: dict | None):
    sys.path.insert(0, str(Path(__file__).parent))
    from google_sheets import update_prize_results, append_purchase_rows

    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    new_round = win_round + 1
    purchase_date = now_kst().strftime('%Y-%m-%d %H:%M:%S')

    new_entry = {
        'round': new_round,
        'purchase_date': purchase_date,
        'draw_date': next_saturday(),
        'tickets': tickets,
        'result': {
            'winning_numbers': [], 'bonus_number': 0,
            'checked': False, 'tickets': [],
        },
    }
    data['lotto645'].append(new_entry)
    PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if prize_result:
        updated = update_prize_results('lotto645', prize_result['round'], prize_result['ticket_results'])
        logging.info('Sheets: updated %d prize rows for round %d', updated, prize_result['round'])
        set_pending_sheets_round(0)

    append_purchase_rows('lotto645', new_entry)
    logging.info('Sheets: appended 5 rows for round %d', new_round)


def main():
    dry_run = '--dry-run' in sys.argv

    # dry-run 시 lock 파일 생성/삭제 건너뜀 (스펙: "파일 수정 없음")
    if not dry_run:
        if LOCK_PATH.exists():
            print('Already running (lock file exists). Exiting.', file=sys.stderr)
            sys.exit(1)
        LOCK_PATH.write_text(str(os.getpid()))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
        ],
    )

    logging.info('=== lotto645 automation start ===')

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
                sys.path.insert(0, str(Path(__file__).parent))
                from google_sheets import update_prize_results
                purchases = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
                pending_entry = next(
                    (e for e in purchases['lotto645']
                     if e['round'] == pending_round and e['result']['checked']),
                    None
                )
                if pending_entry:
                    updated = update_prize_results('lotto645', pending_round, pending_entry['result']['tickets'])
                    logging.info('Sheets retry: %d rows updated for round %d', updated, pending_round)
                    set_pending_sheets_round(0)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
            try:
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()

                logging.info('STEP 1: Fetching winning numbers...')
                win_info = fetch_winning_numbers(page)
                logging.info('Round %d | %s | Bonus: %d', win_info['round'], win_info['numbers'], win_info['bonus'])

                logging.info('STEP 2: Checking prizes...')
                prize_result = check_prizes(win_info, dry_run=dry_run)

                if not dry_run:
                    logging.info('STEP 3: Purchasing tickets...')
                    tickets = purchase_tickets(page)

                    logging.info('STEP 4: Updating Google Sheets...')
                    save_and_update_sheets(win_info['round'], tickets, prize_result)

                    update_last_run('success', win_info['round'])
                    logging.info('=== lotto645 automation complete ===')
                else:
                    logging.info('[DRY-RUN] STEP 3+4 skipped. Prize result: %s', prize_result)
            finally:
                browser.close()

    except Exception as e:
        logging.error(str(e))
        if not dry_run:
            try:
                update_last_run('error', 0, str(e))
            except Exception:
                pass
        sys.exit(1)
    finally:
        if not dry_run:
            LOCK_PATH.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 단위 테스트 재실행 (check_prize 포함 확인)**

```bash
pytest tests/test_lotto645.py -v
```

Expected: 7 passed

- [ ] **Step 3: --dry-run 테스트 (구매 없이 STEP 1~2 확인)**

```bash
python scripts/lotto645_runner.py --dry-run
```

Expected:
- STEP 1 당첨번호 조회 성공 (회차/숫자 출력)
- STEP 2 당첨 확인 계산 (unchecked 항목이 있으면 계산, 없으면 "skipping" 메시지)
- `[DRY-RUN] STEP 3+4 skipped` 출력
- lotto645_purchases.json 변경 없음

- [ ] **Step 4: 커밋**

```bash
git add scripts/lotto645_runner.py tests/test_lotto645.py
git commit -m "feat: lotto645_runner.py Python 구현 완료"
```

---

## Task 5: pension720 check_prize 단위 테스트 (TDD)

**Files:**
- Create: `tests/test_pension720.py`
- Create: `scripts/pension720_runner.py` (check_prize만)

- [ ] **Step 1: 실패하는 테스트 작성**

`tests/test_pension720.py`:
```python
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
    assert check_prize(1, '111710', 1, '307710') == {'rank': '5th', 'prize': 10000}


def test_6th_prize():
    # 뒤 2자리 일치
    assert check_prize(1, '111110', 1, '307710') == {'rank': '6th', 'prize': 2000}


def test_7th_prize():
    # 뒤 1자리 일치
    assert check_prize(1, '111111', 1, '307710') == {'rank': '7th', 'prize': 1000}


def test_no_prize():
    assert check_prize(1, '111111', 1, '307712') == {'rank': 'no prize', 'prize': 0}
```

- [ ] **Step 2: check_prize만 포함한 스켈레톤 작성**

`scripts/pension720_runner.py` (check_prize만):
```python
def check_prize(ticket_group: int, ticket_numbers: str, win_group: int, win_numbers: str) -> dict:
    group_match = ticket_group == win_group
    if group_match and ticket_numbers == win_numbers: return {'rank': '1st', 'prize': 0}
    if not group_match and ticket_numbers == win_numbers: return {'rank': '2nd', 'prize': 0}
    if ticket_numbers[-5:] == win_numbers[-5:]: return {'rank': '3rd', 'prize': 1000000}
    if ticket_numbers[-4:] == win_numbers[-4:]: return {'rank': '4th', 'prize': 100000}
    if ticket_numbers[-3:] == win_numbers[-3:]: return {'rank': '5th', 'prize': 10000}
    if ticket_numbers[-2:] == win_numbers[-2:]: return {'rank': '6th', 'prize': 2000}
    if ticket_numbers[-1:] == win_numbers[-1:]: return {'rank': '7th', 'prize': 1000}
    return {'rank': 'no prize', 'prize': 0}
```

- [ ] **Step 3: 테스트 실행 → 통과 확인**

```bash
pytest tests/test_pension720.py -v
```

Expected: 8 passed

---

## Task 6: pension720_runner.py 전체 구현

**Files:**
- Modify: `scripts/pension720_runner.py` (전체 교체)

- [ ] **Step 1: 전체 pension720_runner.py 작성**

```python
#!/usr/bin/env python3
"""
pension720_runner.py
Pension Lottery 720+ automation: fetch results → check prizes → purchase → update Sheets
Exit 0 on success, 1 on failure (used by n8n IF node).
"""

import sys
import os
import json
import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).parent.parent
CHROME_PATH = r'C:\Program Files\Google\Chrome\Application\chrome.exe'
PURCHASES_PATH = ROOT / 'data' / 'pension720_purchases.json'
LAST_RUN_PATH = ROOT / 'data' / 'last_run.json'
LOG_PATH = ROOT / 'logs' / 'pension720.log'
LOCK_PATH = ROOT / 'data' / 'pension720.lock'

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


def now_kst() -> datetime:
    return datetime.now(KST)


def next_thursday() -> str:
    d = now_kst()
    days_ahead = (3 - d.weekday()) % 7 or 7  # 3=목요일, or 7: 오늘이 목요일이면 다음 주
    return (d + timedelta(days=days_ahead)).strftime('%Y-%m-%d')


def check_prize(ticket_group: int, ticket_numbers: str, win_group: int, win_numbers: str) -> dict:
    group_match = ticket_group == win_group
    if group_match and ticket_numbers == win_numbers: return {'rank': '1st', 'prize': 0}
    if not group_match and ticket_numbers == win_numbers: return {'rank': '2nd', 'prize': 0}
    if ticket_numbers[-5:] == win_numbers[-5:]: return {'rank': '3rd', 'prize': 1000000}
    if ticket_numbers[-4:] == win_numbers[-4:]: return {'rank': '4th', 'prize': 100000}
    if ticket_numbers[-3:] == win_numbers[-3:]: return {'rank': '5th', 'prize': 10000}
    if ticket_numbers[-2:] == win_numbers[-2:]: return {'rank': '6th', 'prize': 2000}
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

        const winGroup = parseInt(wrap?.querySelector('.pension-jo')?.textContent?.trim() || '0');

        const digits = [1,2,3,4,5,6].map(i =>
            wrap?.querySelector(`.wf-${i}n`)?.textContent?.trim() || '0'
        );
        const winNumbers = digits.join('');

        return { round, winGroup, winNumbers, drawDate };
    }""")

    if not result['round'] or not result['winGroup'] or len(result['winNumbers']) != 6:
        raise RuntimeError(f"Failed to fetch pension winning numbers. Got: {result}")
    return result


# STEP 2: 지난 회차 당첨 확인
def check_prizes(win_info: dict, dry_run: bool = False) -> dict | None:
    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    entry = next(
        (e for e in data['pension720']
         if not e['result']['checked'] and e['round'] == win_info['round']),
        None
    )
    if not entry:
        logging.info('No unchecked entry for round %d, skipping prize check.', win_info['round'])
        return None

    ticket_results = []
    for ticket in entry['tickets']:
        r = check_prize(ticket['group'], ticket['numbers'], win_info['winGroup'], win_info['winNumbers'])
        ticket_results.append({'no': ticket['no'], 'rank': r['rank'], 'prize': r['prize']})

    total = sum(t['prize'] for t in ticket_results)
    logging.info('Prize check done for round %d. Total: %d KRW', entry['round'], total)

    if not dry_run:
        entry['result'] = {
            'winning_group': win_info['winGroup'],
            'winning_numbers': win_info['winNumbers'],
            'checked': True,
            'tickets': ticket_results,
            'total_prize': total,
        }
        PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))
        set_pending_sheets_round(entry['round'])

    return {'round': entry['round'], 'ticket_results': ticket_results}


# STEP 3: 5게임 자동구매
def purchase_tickets(page) -> list:
    page.on('dialog', lambda d: d.accept())

    logging.info('Navigating to login page...')
    page.goto('https://www.dhlottery.co.kr/login', wait_until='networkidle', timeout=30000)
    page.wait_for_selector('#inpUserId', timeout=10000)
    page.fill('#inpUserId', os.environ['DHLOTTERY_ID'])
    page.fill('#inpUserPswdEncn', os.environ['DHLOTTERY_PW'])
    page.click('#btnLogin')
    page.wait_for_load_state('networkidle', timeout=30000)

    is_logged_in = page.evaluate(
        "() => !!document.querySelector('#gnb_logout, .btn_logout, [href*=\"logout\"]')"
    )
    if not is_logged_in:
        raise RuntimeError('Login failed: check DHLOTTERY_ID/PW or CAPTCHA')
    logging.info('Login successful')

    page.goto(
        'https://el.dhlottery.co.kr/game/TotalGame.jsp?LottoId=LP72',
        wait_until='networkidle', timeout=30000
    )

    frame_el = page.query_selector('iframe#ifrm_tab')
    frame = frame_el.content_frame() if frame_el else page.main_frame()

    # 당회차 바로구매
    frame.evaluate("""() => {
        const link = Array.from(document.querySelectorAll('a'))
            .find(a => a.textContent.trim() === '당회차 바로구매');
        if (link) link.click();
    }""")
    time.sleep(1.5)

    # 자동번호
    frame.click('a.lotto720_btn_auto_number')
    time.sleep(1)

    # 선택완료
    frame.click('a.lotto720_btn_confirm_number')
    time.sleep(1)

    # 구매하기
    frame.click('a.lotto720_btn_pay')
    time.sleep(1.5)

    # 확인 팝업에서 티켓 번호 추출 (doOrderRequest 클릭 전)
    tickets = frame.evaluate("""() => {
        const items = Array.from(document.querySelectorAll('li[class*="confirm"]'));
        const fromLi = items.map((li, idx) => {
            const m = li.className.match(/confirm(\\d)(\\d{6})/);
            if (m) return { no: idx + 1, group: parseInt(m[1]), numbers: m[2], type: 'auto' };
            return null;
        }).filter(Boolean);
        if (fromLi.length > 0) return fromLi;

        const spans = Array.from(document.querySelectorAll('span.lotto720_popup_confirm_str'));
        return spans.map((span, idx) => {
            const m = span.textContent.trim().match(/(\\d)조\\s+(\\d{6})/);
            if (m) return { no: idx + 1, group: parseInt(m[1]), numbers: m[2], type: 'auto' };
            return null;
        }).filter(Boolean);
    }""")

    # 최종 구매 확인
    frame.click('a[onclick="doOrderRequest()"]')
    time.sleep(2)

    if not tickets:
        raise RuntimeError('Could not extract purchased pension ticket numbers')
    logging.info('Purchased %d tickets', len(tickets))
    return tickets


# STEP 4: purchases.json 저장 + Sheets 업데이트
def save_and_update_sheets(win_round: int, tickets: list, prize_result: dict | None):
    sys.path.insert(0, str(Path(__file__).parent))
    from google_sheets import update_prize_results, append_purchase_rows

    data = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
    new_round = win_round + 1
    purchase_date = now_kst().strftime('%Y-%m-%d %H:%M:%S')

    new_entry = {
        'round': new_round,
        'purchase_date': purchase_date,
        'draw_date': next_thursday(),
        'tickets': tickets,
        'result': {
            'winning_group': 0, 'winning_numbers': '',
            'checked': False, 'tickets': [],
        },
    }
    data['pension720'].append(new_entry)
    PURCHASES_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    if prize_result:
        updated = update_prize_results('pension720', prize_result['round'], prize_result['ticket_results'])
        logging.info('Sheets: updated %d prize rows for round %d', updated, prize_result['round'])
        set_pending_sheets_round(0)

    append_purchase_rows('pension720', new_entry)
    logging.info('Sheets: appended 5 rows for round %d', new_round)


def main():
    dry_run = '--dry-run' in sys.argv

    # dry-run 시 lock 파일 생성/삭제 건너뜀 (스펙: "파일 수정 없음")
    if not dry_run:
        if LOCK_PATH.exists():
            print('Already running (lock file exists). Exiting.', file=sys.stderr)
            sys.exit(1)
        LOCK_PATH.write_text(str(os.getpid()))

    logging.basicConfig(
        level=logging.INFO,
        format='[%(asctime)s] %(message)s',
        datefmt='%Y-%m-%dT%H:%M:%S',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(LOG_PATH, encoding='utf-8'),
        ],
    )

    logging.info('=== pension720 automation start ===')

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
                sys.path.insert(0, str(Path(__file__).parent))
                from google_sheets import update_prize_results
                purchases = json.loads(PURCHASES_PATH.read_text(encoding='utf-8'))
                pending_entry = next(
                    (e for e in purchases['pension720']
                     if e['round'] == pending_round and e['result']['checked']),
                    None
                )
                if pending_entry:
                    updated = update_prize_results('pension720', pending_round, pending_entry['result']['tickets'])
                    logging.info('Sheets retry: %d rows updated for round %d', updated, pending_round)
                    set_pending_sheets_round(0)

        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
            try:
                context = browser.new_context(user_agent=USER_AGENT)
                page = context.new_page()

                logging.info('STEP 1: Fetching winning numbers...')
                win_info = fetch_winning_numbers(page)
                logging.info('Round %d | Group: %d | Numbers: %s', win_info['round'], win_info['winGroup'], win_info['winNumbers'])

                logging.info('STEP 2: Checking prizes...')
                prize_result = check_prizes(win_info, dry_run=dry_run)

                if not dry_run:
                    logging.info('STEP 3: Purchasing tickets...')
                    tickets = purchase_tickets(page)

                    logging.info('STEP 4: Updating Google Sheets...')
                    save_and_update_sheets(win_info['round'], tickets, prize_result)

                    update_last_run('success', win_info['round'])
                    logging.info('=== pension720 automation complete ===')
                else:
                    logging.info('[DRY-RUN] STEP 3+4 skipped. Prize result: %s', prize_result)
            finally:
                browser.close()

    except Exception as e:
        logging.error(str(e))
        if not dry_run:
            try:
                update_last_run('error', 0, str(e))
            except Exception:
                pass
        sys.exit(1)
    finally:
        if not dry_run:
            LOCK_PATH.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
```

- [ ] **Step 2: 단위 테스트 재실행**

```bash
pytest tests/test_pension720.py -v
```

Expected: 8 passed

- [ ] **Step 3: --dry-run 테스트**

```bash
python scripts/pension720_runner.py --dry-run
```

Expected:
- STEP 1 당첨번호 조회 성공 (회차/조/번호 출력)
- STEP 2 당첨 확인 (또는 skipping)
- `[DRY-RUN] STEP 3+4 skipped`
- pension720_purchases.json 변경 없음

- [ ] **Step 4: 커밋**

```bash
git add scripts/pension720_runner.py tests/test_pension720.py
git commit -m "feat: pension720_runner.py Python 구현 완료"
```

---

## Task 7: test_runner.py

**Files:**
- Create: `scripts/test_runner.py`

- [ ] **Step 1: test_runner.py 작성**

```python
#!/usr/bin/env python3
"""
test_runner.py
n8n 파이프라인 스모크 테스트용 스크립트. 브라우저/구매 없이 exit code만 반환.
Usage:
    python scripts/test_runner.py          # exit 0 (성공 시뮬레이션)
    python scripts/test_runner.py --fail   # exit 1 (실패 시뮬레이션)
"""

import sys

if '--fail' in sys.argv:
    print('{"exitCode": 1, "stderr": "test failure simulation"}', file=sys.stderr)
    sys.exit(1)
else:
    print('{"exitCode": 0}')
    sys.exit(0)
```

- [ ] **Step 2: 두 가지 exit code 확인**

```bash
python scripts/test_runner.py; echo "exit: $?"
python scripts/test_runner.py --fail; echo "exit: $?"
```

Expected:
- 첫 번째: `{"exitCode": 0}` 출력, `exit: 0`
- 두 번째: `exit: 1`

- [ ] **Step 3: 커밋**

```bash
git add scripts/test_runner.py
git commit -m "feat: test_runner.py Python 스모크 테스트 스크립트"
```

---

## Task 8: CLAUDE.md 업데이트

**Files:**
- Modify: `CLAUDE.md`

- [ ] **Step 1: CLAUDE.md에 Python 실행 명령어 추가**

CLAUDE.md의 "Running scripts" 섹션을 아래와 같이 교체:

```markdown
## Running scripts

```bash
# Python 자동화 (테스트용 수동 실행)
python scripts/lotto645_runner.py --dry-run   # STEP 1~2만 실행, 구매 없음
python scripts/pension720_runner.py --dry-run

python scripts/lotto645_runner.py             # 전체 실행 (DHLOTTERY_ID/PW 필요)
python scripts/pension720_runner.py

# 파이프라인 스모크 테스트 (브라우저/구매 없음)
python scripts/test_runner.py           # exit 0
python scripts/test_runner.py --fail    # exit 1

# 의존성 설치 (최초 1회)
pip install -r requirements.txt
playwright install chromium
```

Required environment variables: `DHLOTTERY_ID`, `DHLOTTERY_PW`
```

- [ ] **Step 2: 커밋**

```bash
git add CLAUDE.md
git commit -m "docs: CLAUDE.md Python 실행 명령어 업데이트"
```

---

## Task 9: n8n 업데이트 + 검증 + JS 파일 정리

**Files:**
- Delete (n8n 1회 성공 후): `scripts/lotto645_runner.js`, `scripts/pension720_runner.js`, `scripts/google_sheets.js`, `scripts/test_runner.js`, `scripts/setup_google_auth.js`, `scripts/check_sheets.js`, `package.json`, `config/credentials.json`, `config/token.json`

- [ ] **Step 1: n8n Execute Command 노드 명령어 수정**

n8n에서 아래와 같이 lotto645 Execute Command 노드 명령어를 변경:

```
# 기존
cmd /c "set DHLOTTERY_ID=... && node C:\...\scripts\lotto645_runner.js"

# 변경 후
cmd /c "set DHLOTTERY_ID=%DHLOTTERY_ID% && set DHLOTTERY_PW=%DHLOTTERY_PW% && <python-path> <local-existing-service-root>\scripts\lotto645_runner.py"
```

pension720도 동일하게 수정 (`lotto645_runner.py` → `pension720_runner.py`).

> Python 경로 확인: `where python` 명령어로 확인. venv 사용 시 venv 내 python.exe 경로 사용.

- [ ] **Step 2: n8n 수동 1회 실행 확인**

n8n UI에서 lotto645 워크플로우 수동 실행 → 성공 확인 (exit 0, Telegram 알림).
pension720 워크플로우도 동일하게 확인.

- [ ] **Step 3: 검증 후 JS 파일 삭제**

n8n에서 Python 버전이 1회 이상 성공한 것을 확인한 뒤:

```bash
git rm scripts/lotto645_runner.js 2>/dev/null || true
git rm scripts/pension720_runner.js 2>/dev/null || true
git rm scripts/google_sheets.js 2>/dev/null || true
git rm scripts/test_runner.js 2>/dev/null || true
git rm scripts/setup_google_auth.js 2>/dev/null || true
git rm scripts/check_sheets.js 2>/dev/null || true
git rm package.json 2>/dev/null || true
git rm config/credentials.json config/token.json 2>/dev/null || true
git commit -m "chore: Node.js 파일 삭제 (Python 마이그레이션 완료)"
```

> `credentials.json`, `token.json`, `check_sheets.js` 등은 .gitignore 또는 미추적 상태일 수 있어 `|| true`로 오류 무시.

---

## 전체 테스트 실행

```bash
pytest tests/ -v
```

Expected: 15 passed (test_lotto645.py 7개 + test_pension720.py 8개)
