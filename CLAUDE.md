# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Automates weekly Dong-Haeng Lottery ticket purchases and prize checking:
- **Lotto 6/45**: draws every Saturday → automation runs every Monday 10:00 (일요일은 모바일 구매 불가)
- **Pension Lottery 720+**: draws every Thursday → automation runs every Friday 10:00

Each run: (1) fetches latest winning numbers via Playwright, (2) checks prizes for last week's unchecked tickets, (3) purchases 5 new auto-number tickets, (4) logs results to Google Sheets.

Triggered by n8n workflows (Docker). On success/failure, n8n sends a Telegram notification.

## 자동화 상태 확인

```bash
# 로컬: 마지막 실행 시각, 미구매 회차, 미확인 당첨, 락 파일 유무
python3 scripts/check_status.py

# GCP: 실행 로그 실시간 확인
tail -f /home/ubuntu/lottery_auto/logs/lotto645.log
tail -f /home/ubuntu/lottery_auto/logs/pension720.log

# GCP: 타임아웃으로 강제 종료됐는지 확인
grep "timeout" /home/ubuntu/lottery_auto/logs/lotto645.log
grep "timeout" /home/ubuntu/lottery_auto/logs/pension720.log

# GCP: hang 중인 프로세스 확인
ps aux | grep python3

# GCP: hang 프로세스 강제 종료 (ubuntu 유저로)
sudo kill <PID>
```

**n8n은 Docker 아닌 systemd로 실행 중** (`/etc/systemd/system/n8n.service`). GCP 서버: `<your-gcp-ip>`

```bash
# n8n 상태 확인
systemctl status n8n

# n8n 로그
journalctl -u n8n --since "1 hour ago"
```

## GCP 서버 GitHub 배포

**GCP remote는 SSH로 설정됨** — HTTPS로 절대 변경하지 말 것.

```bash
# 코드 배포 (로컬에서 push 후 GCP에서 pull)
sudo -u ubuntu git -C /home/ubuntu/lottery_auto pull

# remote 확인 (git@github.com: 형태여야 함)
git -C /home/ubuntu/lottery_auto remote -v
```

SSH key 위치: `/home/ubuntu/.ssh/id_ed25519` (ubuntu 유저 소유)
- pull은 반드시 `sudo -u ubuntu`로 실행
- git pull 실패 시 remote URL 먼저 확인 (`git remote -v`), HTTPS로 바뀌어 있으면 SSH로 복원:
  ```bash
  git remote set-url origin git@github.com:dayeonisme/lottery-pension-auto.git
  ```

## GCP 서버 수동 실행 시 주의사항

GCP SSH 세션에서는 heredoc(`<< 'EOF'`) 사용 시 터미널이 들여쓰기를 자동 추가하여 EOF 종료 토큰을 인식하지 못하는 문제가 있다. 임시 Python 스크립트 실행이 필요할 때는 heredoc 대신 `python3 -c "..."` 한 줄 방식을 사용한다.

```bash
# 수동 실행 (ubuntu 유저 + 환경변수 한 번에) — data/ 파일이 ubuntu 소유(644)라 이 방식만 작동
sudo -u ubuntu env $(sudo cat /etc/n8n/env | xargs) python3 /home/ubuntu/lottery_auto/scripts/pension720_runner.py
sudo -u ubuntu env $(sudo cat /etc/n8n/env | xargs) python3 /home/ubuntu/lottery_auto/scripts/lotto645_runner.py
```

> **주의**: `export $(...)` 후 별도 실행하면 `sudo -u ubuntu` 전환 시 환경변수가 전달되지 않아 `DHLOTTERY_ID/PW not set` 오류 발생.

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

## Architecture

```
n8n (Docker) ──schedules──▶ python scripts/{runner}.py ──▶ Telegram notification
                                    │
              ┌─────────────────────┤
              ▼                     ▼
         playwright              gspread
      (Chromium headless)   (service account auth)
              │                     │
        dhlottery.co.kr       Google Sheets
                               [SPREADSHEET_ID in google_sheets.py]
```

**scripts/google_sheets.py** — shared module required by both runners. Manages service account auth (reads `config/service_account.json`), exposes two functions:
- `update_prize_results(lottery_type, round, ticket_results)` — finds rows by lottery type + round in `raw` sheet, batch-updates columns H–K
- `append_purchase_rows(lottery_type, purchase_data)` — appends 5 new rows to `raw` sheet

Both runners follow the identical 4-step pattern: fetch → check → purchase → Sheets.

## Key data files

| File | Purpose |
|------|---------|
| `data/lotto645_purchases.json` | Array under `lotto645` key. Each entry has `round`, `tickets[]`, `result.checked` |
| `data/pension720_purchases.json` | Array under `pension720` key. Same structure; tickets have `group` + 6-digit `numbers` string |
| `data/last_run.json` | Tracks `status`, `last_round`, `pending_sheets_round` per lottery type |
| `config/service_account.json` | Google service account key for Sheets/Drive API auth |

## Critical invariants

**Round validation**: STEP 2 only checks prizes for an entry whose `round === winInfo.round` (the round returned by STEP 1). Never applies winning numbers to a future round.

**Duplicate-run protection**: A `.lock` file (`data/lotto645.lock` / `data/pension720.lock`) is created at start and deleted in `finally`. If the process finds an existing lock it exits immediately.

**Pending Sheets recovery**: After STEP 2 writes prizes to JSON, `pending_sheets_round` is set in `last_run.json`. It is cleared only after the Sheets update succeeds. On the next run, if `pending_sheets_round > 0`, the Sheets update is retried before proceeding. 해당 회차의 `checked` 엔트리가 없으면 stale 플래그로 간주하고 즉시 0으로 초기화.

**Run timeout**: `signal.alarm(600)` — `logging.basicConfig()` 직후, 모든 I/O 작업 이전에 설정. 600초 초과 시 `os._exit(1)` 강제 종료. 타임아웃 발생 시 로그에 `600s timeout — force exit` 기록됨.

**KST dates**: All date calculations (`next_saturday`, `next_thursday`, `purchase_date`, `draw_confirmed_date`) use `datetime.now(timezone(timedelta(hours=9)))` for Korea Standard Time.

## MCP servers (Claude Code)

Configured in `config/mcp_config.json` (reference only). The operative config written to `%APPDATA%\Claude\claude_desktop_config.json` uses `cmd /c npx` wrappers required on Windows:
- **puppeteer**: headless Chrome automation
- **gdrive**: Google Drive read/write (`GDRIVE_CREDENTIALS_PATH` → `config/credentials.json`)

## Google Sheets layout

Single sheet named **`raw`**, columns A–K:
`lottery_type | purchase_datetime | round | ticket_no | numbers | purchase_amount | draw_date | result | prize_rank | prize_amount | draw_confirmed_date`

`lottery_type` values: `로또6/45` / `연금복권720+` (Korean display names defined in `LOTTERY_DISPLAY_NAME` in google_sheets.py).
