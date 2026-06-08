# Python Migration Design

**Date:** 2026-03-22
**Project:** lottery_auto
**Goal:** Node.js → Python 마이그레이션

---

## 배경

현재 lottery_auto는 Node.js(puppeteer-core + googleapis)로 작성되어 있음. 유지보수자가 Python만 알고 있어 직접 수정이 불가능한 상황. Python으로 마이그레이션하여 독립적인 유지보수 가능하도록 함.

---

## 기술 스택 결정

| 항목 | 기존 (Node.js) | 변경 후 (Python) |
|------|--------------|-----------------|
| 브라우저 자동화 | puppeteer-core | playwright (sync API) |
| Google Sheets | googleapis | gspread |
| Google 인증 | OAuth2 (token.json) | 서비스 계정 (service_account.json) |
| 코드 스타일 | async/await | 동기(sync) |
| 스케줄러 | n8n (Docker) | n8n (변경 없음) |

---

## 파일 구조

```
lottery_auto/
├── scripts/
│   ├── lotto645_runner.py         # Lotto 6/45 자동화 (신규)
│   ├── pension720_runner.py       # Pension 720+ 자동화 (신규)
│   ├── google_sheets.py           # 공유 Sheets 헬퍼 (신규)
│   ├── test_runner.py             # 파이프라인 스모크 테스트 (신규)
│   └── setup_service_account.md  # 서비스 계정 발급 가이드 (문서)
├── config/
│   └── service_account.json       # 서비스 계정 키 (gitignore, 수동 발급)
├── requirements.txt
└── data/, logs/                   # 기존 JSON 형식 그대로 유지
```

기존 JS 파일은 Python 버전이 n8n에서 1회 이상 성공한 뒤 삭제.

---

## 의존성

```
playwright
gspread
google-auth
```

설치:
```bash
pip install -r requirements.txt
playwright install chromium
```

> playwright, gspread, google-auth 모두 최신 안정 버전 사용. 버전 고정이 필요하면 설치 후 `pip freeze > requirements.txt`로 확정.

---

## 아키텍처

### google_sheets.py

```python
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

# 한국어 표시명 (Google Sheets A열 값과 반드시 일치해야 함)
LOTTERY_DISPLAY_NAME = {
    'lotto645': '로또6/45',
    'pension720': '연금복권720+',
}

def get_client():
    # gspread 6.x 올바른 서비스 계정 인증 방식
    creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_PATH, scopes=SCOPES)
    return gspread.Client(auth=creds)

def update_prize_results(lottery_type: str, round_no: int, ticket_results: list) -> int:
    """raw 시트에서 lottery_type + round_no 행을 찾아 H~K 열 업데이트. 반환: 업데이트된 행 수"""

def append_purchase_rows(lottery_type: str, purchase_data: dict) -> None:
    """raw 시트 하단에 티켓 1장당 1행씩 추가"""
```

**Google Sheets 컬럼 포맷 규칙** (기존 데이터와 반드시 호환):

| lottery_type | E열 (numbers) 포맷 | 예시 |
|---|---|---|
| lotto645 | 6개 숫자를 2자리 zero-padding 후 공백 구분 | `"03 14 15 23 24 37"` |
| pension720 | `{group}-{6자리번호}` | `"1-307710"` |

### lotto645_runner.py / pension720_runner.py

```python
import sys, os, json, time, logging
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).parent.parent

def fetch_winning_numbers(page) -> dict: ...   # STEP 1
def check_prizes(win_info: dict) -> dict | None: ...  # STEP 2
def purchase_tickets(page) -> list: ...        # STEP 3
def save_and_update_sheets(...): ...           # STEP 4

def main():
    dry_run = '--dry-run' in sys.argv

    # lock 파일 확인 (중복 실행 방지)
    if LOCK_PATH.exists():
        sys.exit(1)
    LOCK_PATH.write_text(str(os.getpid()))

    try:
        # last_run.json 없으면 기본값으로 초기화
        if not LAST_RUN_PATH.exists():
            _init_last_run()

        # pending_sheets_round 재시도
        ...

        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
            try:
                page = browser.new_page()
                win_info = fetch_winning_numbers(page)   # STEP 1
                prize_result = check_prizes(win_info)     # STEP 2 (dry_run 시 파일 수정 없음)
                if not dry_run:
                    tickets = purchase_tickets(page)      # STEP 3
                    save_and_update_sheets(...)            # STEP 4
            finally:
                browser.close()
    except Exception as e:
        logging.error(e)
        sys.exit(1)
    finally:
        LOCK_PATH.unlink(missing_ok=True)  # 항상 lock 삭제
```

---

## 복권별 당첨 판정 로직

### lotto645 — 정수 리스트 비교
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

### pension720 — 문자열 슬라이싱 비교 (6자리 숫자 문자열)
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

---

## Node.js → Python 주요 변환표

| Node.js | Python |
|---------|--------|
| `process.env['X']` | `os.environ['X']` |
| `fs.readFileSync` / `writeFileSync` | `json.load()` / `json.dump()` |
| `fs.existsSync` / `unlinkSync` | `Path.exists()` / `Path.unlink(missing_ok=True)` |
| `page.waitForSelector(sel)` | `page.wait_for_selector(sel)` |
| `frame.evaluate(() => {...})` | `frame.evaluate("() => {...}")` |
| `setTimeout(r, N)` | `time.sleep(N / 1000)` |
| `page.on('dialog', async d => d.accept())` | `page.on("dialog", lambda d: d.accept())` |
| `console.log` + `fs.appendFileSync` | `logging` 모듈 (파일 핸들러 추가) |
| `process.exit(0/1)` | `sys.exit(0/1)` |
| `path.resolve(__dirname, '..')` | `Path(__file__).parent.parent` |

---

## --dry-run 플래그

```bash
python scripts/lotto645_runner.py --dry-run
```

- STEP 1 (당첨번호 조회) + STEP 2 (당첨 확인 계산) 만 실행
- **파일 수정 없음**: `purchases.json`, `last_run.json`, lock 파일 모두 변경하지 않음
- STEP 3 (구매), STEP 4 (Sheets 업데이트) 건너뜀
- 결과는 콘솔 출력만

---

## 날짜 계산 (KST 기준)

모든 날짜는 KST(UTC+9) 기준으로 계산:

```python
from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))

def now_kst() -> datetime:
    return datetime.now(KST)

def next_saturday() -> str:
    d = now_kst()
    days_ahead = (5 - d.weekday()) % 7 or 7  # 5=토요일
    return (d + timedelta(days=days_ahead)).strftime('%Y-%m-%d')

def next_thursday() -> str:
    d = now_kst()
    days_ahead = (3 - d.weekday()) % 7 or 7  # 3=목요일
    return (d + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
```

> `or 7`: 오늘이 토/목요일인 경우 당일이 아닌 다음 주로 계산 (Node.js `|| 7`과 동일).

---

## last_run.json 초기화

파일이 없을 때 기본값으로 생성:

```python
DEFAULT_LAST_RUN = {
    'lotto645': {
        'last_run': None, 'last_success': None, 'last_round': 0,
        'pending_sheets_round': 0, 'status': 'never', 'last_error': None
    },
    'pension720': {
        'last_run': None, 'last_success': None, 'last_round': 0,
        'pending_sheets_round': 0, 'status': 'never', 'last_error': None
    }
}
```

---

## test_runner.py

```bash
python scripts/test_runner.py          # 성공 시뮬레이션 (exit 0)
python scripts/test_runner.py --fail   # 실패 시뮬레이션 (exit 1)
```

n8n 파이프라인 검증용. 브라우저/구매 없이 exit code만 반환.

---

## n8n 변경사항

Execute Command 노드 전체 명령어 (Windows 환경):

```
# 기존
cmd /c "set DHLOTTERY_ID=... && node C:\...\scripts\lotto645_runner.js"

# 변경 후 (Python 절대경로 사용)
cmd /c "set DHLOTTERY_ID=%DHLOTTERY_ID% && set DHLOTTERY_PW=%DHLOTTERY_PW% && <python-path> <local-existing-service-root>\scripts\lotto645_runner.py"
```

> Python 실행파일 경로는 `where python` 명령어로 확인. venv 사용 시 venv 내 python.exe 경로 사용.

---

## 서비스 계정 설정 (1회)

1. Google Cloud Console → IAM → 서비스 계정 생성
2. JSON 키 다운로드 → `config/service_account.json` 저장
3. 스프레드시트에 서비스 계정 이메일을 **편집자**로 공유
4. `.gitignore`에 `config/service_account.json` 추가

---

## .gitignore 추가

```
config/service_account.json
```

---

## 마이그레이션 순서

1. `requirements.txt` 작성 + `pip install` + `playwright install chromium`
2. `google_sheets.py` 작성 + 단독 연결 테스트 (시트 목록 출력)
3. `lotto645_runner.py` 작성 + `--dry-run` 테스트 (구매 없이 STEP 1~2 확인)
4. `pension720_runner.py` 작성 + `--dry-run` 테스트
5. `test_runner.py` 작성 + n8n 파이프라인 스모크 테스트
6. n8n Execute Command 노드 명령어 수정 → 수동 1회 실행 확인
7. 기존 JS 파일 삭제 (n8n 성공 확인 후)
