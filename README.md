# lottery-pension-auto

Lotto 6/45와 연금복권 720+ 구매, 당첨 결과 확인, Google Sheets 기록, Telegram 알림을 자동화하는 Python 프로젝트입니다.

이 저장소는 실행 가능한 자동화 코드를 정리한 공개용 저장소입니다. 개인 실행 데이터, 인증 정보, 로컬 로그는 포함하지 않습니다.

## 주요 기능

- Lotto 6/45 자동화 실행
- 연금복권 720+ 자동화 실행
- 당첨 결과 파싱
- Google Sheets 결과 기록
- Telegram 성공/실패 알림
- 월간·분기 결산 Telegram 알림 (구매 횟수·금액, 등수별 당첨, 총 당첨금)
- 예약 실행을 위한 n8n 워크플로 템플릿
- 토큰 인증 웹훅으로 서버 배포
- 복권 결과 파싱과 당첨 로직 테스트

## 프로젝트 구조

```text
config/
  n8n_lotto645_workflow.json
  n8n_pension720_workflow.json
  n8n_monthly_report_workflow.json   # 월간 결산 (매월 1일)
  n8n_quarterly_report_workflow.json # 분기 결산 (1·4·7·10월 1일)
  n8n_deploy_workflow.json           # 웹훅 배포 (git pull)
scripts/
  google_sheets.py
  lotto645_runner.py
  pension720_runner.py
  monthly_report.py                  # 월간/분기 결산 Telegram 발송
  browser_lite.py                    # Playwright 리소스 차단(경량화)
  gcp_firewall.sh                    # [내 PC] GCP 방화벽을 내 IP로 제한
  gcp_service_account.sh             # [내 PC] Sheets용 서비스 계정·키 발급
  server_setup.sh                    # [서버] n8n 워크플로·배포 토큰 설정
  test_runner.py
  check_status.py                   # 마지막 실행 상태 요약 조회
  install-hooks.sh                   # pre-commit 훅 설치
  pre-commit                         # 커밋 시 비밀정보/개인정보 스캔 훅
tests/
  test_lotto645.py
  test_pension720.py
  test_monthly_report.py
  test_pre_commit_hook.py
pyproject.toml
uv.lock
```

`data/`, `logs/`는 저장소에 없고 최초 실행 시 스크립트가 자동으로 생성합니다.

## 설치

[uv](https://github.com/astral-sh/uv)로 Python 의존성을 설치합니다.

```bash
uv sync
uv run playwright install chromium
```

## Google Sheets 인증 설정

1. Google Cloud Console에서 서비스 계정을 생성합니다.
2. Google Sheets API와 Google Drive API를 활성화합니다.
3. 서비스 계정 JSON 키를 내려받아 아래 경로에 저장합니다.

```text
config/service_account.json
```

4. 기록 대상 Google Spreadsheet를 서비스 계정 이메일에 편집자 권한으로 공유합니다.

## 환경 변수

실행 전에 아래 환경 변수를 설정합니다.

```bash
export GOOGLE_SPREADSHEET_ID="your_google_spreadsheet_id"
export GOOGLE_SERVICE_ACCOUNT_PATH="$PWD/config/service_account.json"
export DHLOTTERY_ID="your_dhlottery_id"
export DHLOTTERY_PW="your_dhlottery_password"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
```

각 변수의 의미는 다음과 같습니다.

| 변수 | 필수 | 의미 |
|------|------|------|
| `GOOGLE_SPREADSHEET_ID` | ✅ | 결과를 기록할 Google Spreadsheet의 ID. 시트 URL `.../d/<ID>/edit`의 `<ID>` 부분 |
| `GOOGLE_SERVICE_ACCOUNT_PATH` | ✅ | 서비스 계정 JSON 키 파일 경로 (기본 `config/service_account.json`) |
| `DHLOTTERY_ID` | ✅ | 동행복권(dhlottery.co.kr) 로그인 아이디 |
| `DHLOTTERY_PW` | ✅ | 동행복권 로그인 비밀번호 |
| `TELEGRAM_BOT_TOKEN` | ⬜ | 알림을 보낼 Telegram 봇 토큰. BotFather에서 발급. 미설정 시 알림만 생략, 자동화는 정상 실행 |
| `TELEGRAM_CHAT_ID` | ⬜ | 알림을 받을 채팅(또는 채널)의 ID. `BOT_TOKEN`과 한 쌍으로 동작 |
| `BROWSER_LITE` | ⬜ | 기본 `1`. `0`이면 Playwright 리소스 차단(`browser_lite.py`)을 끔. 구매 페이지 동작에 문제가 있을 때 배포 없이 롤백용 |

실제 계정 정보, Telegram 토큰, Google 인증 파일은 GitHub에 커밋하지 마세요.

## 수동 실행

브라우저 자동화 없이 흐름만 확인하려면 dry-run으로 실행합니다.

```bash
uv run python3 scripts/lotto645_runner.py --dry-run
uv run python3 scripts/pension720_runner.py --dry-run
```

실제 자동화를 실행합니다.

```bash
uv run python3 scripts/lotto645_runner.py
uv run python3 scripts/pension720_runner.py
```

n8n 명령 파이프라인만 간단히 확인하려면 다음 명령을 사용합니다.

```bash
uv run python3 scripts/test_runner.py
uv run python3 scripts/test_runner.py --fail
```

결산 메시지를 발송 없이 확인합니다(시트 읽기만, 브라우저/구매 없음).

```bash
uv run python3 scripts/monthly_report.py --dry-run                # 지난달
uv run python3 scripts/monthly_report.py --month 2026-08 --dry-run
uv run python3 scripts/monthly_report.py --quarterly --dry-run    # 직전 분기
uv run python3 scripts/monthly_report.py --quarter 2026-Q3 --dry-run
```

### 브라우저 경량화

두 runner는 `scripts/browser_lite.py`로 폰트·미디어 요청을 차단하고, 조회 전용 페이지(메인/당첨결과)의 이미지만 1px로 대체합니다. 로그인·구매 페이지의 이미지는 이미지형 버튼 클릭을 위해 그대로 둡니다. Chromium은 `--renderer-process-limit=1`로 실행됩니다.

## 테스트

```bash
uv run python3 -m pytest tests/
```

## Git hooks

`scripts/pre-commit`은 커밋 시 스테이징된 파일에서 비밀번호/토큰 등 민감정보와 개인 경로를 스캔해 커밋을 막습니다. 최초 1회 설치합니다.

```bash
scripts/install-hooks.sh
```

## n8n 예약 실행

n8n을 서버에 상시 서비스(systemd 등)로 띄워두고, 워크플로마다 **Schedule Trigger + Execute Command** 노드 두 개로 구성합니다. Execute Command 노드가 실행하는 커맨드 예시:

```bash
export $(sudo cat /etc/n8n/env | xargs) && timeout 600 <repo-path>/.venv/bin/python3 <repo-path>/scripts/lotto645_runner.py
```

- `/etc/n8n/env`에 `DHLOTTERY_ID`/`DHLOTTERY_PW`/`GOOGLE_SPREADSHEET_ID`/`TELEGRAM_*` 등 환경 변수를 저장해두고 실행 시 로드합니다.
- Python 실행파일은 `uv sync`로 만든 `.venv/bin/python3`를 직접 지정합니다(uv 자체가 PATH에 없어도 동작).
- `timeout 600`은 스크립트 내부의 600초 alarm과 별개로 n8n 쪽에서도 강제 종료를 보장하기 위한 이중 안전장치입니다.

n8n에서 아래 워크플로 템플릿을 import한 뒤, Execute Command 노드의 커맨드에 있는 경로를 실제 배포 경로로 바꿉니다.

- `config/n8n_lotto645_workflow.json` (Schedule: 매주 월요일 10:00)
- `config/n8n_pension720_workflow.json` (Schedule: 매주 금요일 10:00)
- `config/n8n_monthly_report_workflow.json` (Schedule: 매월 1일 10:00) — `scripts/monthly_report.py`가 Sheets `raw` 시트를 집계해 지난달 구매 횟수·금액, 등수별 당첨 건수, 총 당첨금을 Telegram으로 발송 (`--month YYYY-MM`, `--dry-run` 지원)
- `config/n8n_quarterly_report_workflow.json` (Schedule: 1·4·7·10월 1일 10:00) — `monthly_report.py --quarterly`로 직전 분기 결산 발송 (`--quarter YYYY-Qn` 지원)
- `config/n8n_deploy_workflow.json` (Webhook, POST `/webhook/deploy-lottery-auto`) — 호출 시 서버에서 `git pull --ff-only` 후 최신 커밋을 응답으로 반환. import 후 n8n Credentials에서 **Header Auth**(name: `X-Deploy-Token`, value: 임의의 긴 랜덤 문자열)를 `deploy-token`으로 만들어 Webhook 노드에 연결하고 워크플로를 Active로 켠다. 토큰은 저장소에 커밋하지 않는다.
  ```bash
  curl -X POST https://<n8n주소>/webhook/deploy-lottery-auto -H "X-Deploy-Token: $DEPLOY_TOKEN"
  ```

n8n 스케줄 시각은 n8n의 `GENERIC_TIMEZONE`을 따릅니다. 한국 시간으로 돌리려면 `/etc/n8n/env`에 `GENERIC_TIMEZONE=Asia/Seoul`을 설정하세요.

## 배포

`main`에 머지한 뒤 배포 웹훅을 호출하면 서버가 `git pull --ff-only`를 실행하고 최신 커밋을 응답으로 돌려줍니다. 응답 JSON의 `exitCode`가 `0`이면 성공이며, `stderr`의 `From github.com...`은 git 진행 메시지입니다.

토큰은 셸 프로필에 평문으로 두지 말고 OS 키체인 등에 보관합니다. macOS 예시:

```bash
# 저장 (프롬프트로 입력 → 셸 히스토리에 남지 않음)
security add-generic-password -a "$USER" -s lottery-deploy-token -U -w

# ~/.zshrc
deploy-lottery() {
  local token
  token="$(security find-generic-password -s lottery-deploy-token -w)" || return 1
  curl -sS -X POST http://<n8n주소>:5678/webhook/deploy-lottery-auto -H "X-Deploy-Token: $token"
  echo
}
```

## 서버 보안·인프라 스크립트 (GCP)

| 스크립트 | 실행 위치 | 역할 |
|---|---|---|
| `scripts/gcp_firewall.sh` | 내 PC (gcloud) | n8n(5678)·SSH(22) 인그레스를 내 공인 IP(+콘솔 브라우저 SSH 대역)로 제한. IP가 바뀌면 재실행 |
| `scripts/server_setup.sh <서버IP>` | 서버 | `git pull`, `WEBHOOK_URL` 설정, n8n 서비스 유저로 워크플로·배포 토큰 credential import, 배포 워크플로 활성화 |
| `scripts/gcp_service_account.sh` | 내 PC (gcloud) | 서버 프로젝트에 Sheets/Drive API 활성화, 서비스 계정 생성, 키를 저장소 밖(`~/lottery_sa_key.json`)에 발급 |

```bash
PROJECT_ID=<프로젝트ID> bash scripts/gcp_firewall.sh
PROJECT_ID=<프로젝트ID> bash scripts/gcp_service_account.sh
```

프로젝트 ID, 서버 IP, 계정 이메일, 토큰, 키 파일은 저장소에 기록하지 마세요.

## Telegram 알림 포맷

각 runner는 실행이 끝나면 `send_telegram()`으로 Telegram Bot API(`sendMessage`)에 직접 알림을 보냅니다. `TELEGRAM_BOT_TOKEN`과 `TELEGRAM_CHAT_ID`가 설정되지 않으면 알림은 건너뜁니다.

### 성공 알림

구매 완료 시 구매 번호, 추첨일, 구매시각을 보냅니다. 전주 미확인 회차가 있으면 당첨 결과 섹션이 덧붙습니다.

Lotto 6/45:

```text
[OK] 로또6/45 제1234회 구매 완료

🎟 구매 번호:
  1. 03 12 19 27 33 41
  2. 05 11 22 30 38 44
  ...

📅 추첨일: 2026-06-20
🕐 구매시각: 2026-06-16 10:00

📊 전주 제1233회 당첨 결과:
  1. 5등 (5천원)
  2. 낙첨
  💰 합계: 5,000원
```

연금복권 720+:

```text
[OK] 연금복권720+ 제123회 구매 완료

🎟 구매 번호:
  1조 234567
  3조 891011
  ...

📅 추첨일: 2026-06-19
🕐 구매시각: 2026-06-13 10:00

📊 전주 제122회 당첨 결과:
  1. 7등 (1천원)
  💰 합계: 1,000원
```

1등·2등·3등(연금복권은 1등·2등·보너스) 당첨 시 해당 줄에 `⚠️수동확인`이 붙고, 로그에 `HIGH RANK WIN`이 기록됩니다.

### 결산 알림

`monthly_report.py`가 보내는 월간/분기 결산입니다. 구매는 구매일 기준, 당첨은 당첨 확인일 기준으로 집계합니다(월말 구매분의 당첨은 확인된 달에 포함).

```text
📊 2026년 6월 결산

🎱 로또6/45
  구매: 4회 (20장) / 20,000원
  당첨: 1건
    - 5등: 1건
  당첨금: 5,000원

🎫 연금복권720+
  구매: 4회 (20장) / 20,000원
  당첨: 2건
    - 6등: 1건
    - 7등: 1건
  당첨금: 6,000원

💰 총 구매 40,000원 / 총 당첨 11,000원 / 손익 -29,000원
```

분기 결산은 제목만 `📊 2026년 2분기 결산` 형태이고 나머지 형식은 같습니다. 로또 1~3등, 연금 1·2등·보너스는 시트 당첨금이 `-`로 기록되어 합계에서 빠집니다.

### 실패 알림

예외 발생 시 실행 시각과 에러 메시지를 보냅니다.

```text
[FAIL] lotto645 automation failed

Run time: 2026-06-16 10:00

Error: <에러 메시지>
```

## 주의사항

- 실제 구매 자동화는 계정, 결제, 사이트 정책과 관련될 수 있으므로 사용 전 정책과 책임 범위를 확인하세요.
- 공개 저장소에는 API key, 비밀번호, Telegram Bot Token, Chat ID, Google 서비스 계정 JSON을 올리지 마세요.
- 먼저 `--dry-run`과 테스트로 동작을 확인한 뒤 실제 실행하세요.
