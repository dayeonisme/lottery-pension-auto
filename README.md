# lottery-pension-auto

Lotto 6/45와 연금복권 720+ 구매, 당첨 결과 확인, Google Sheets 기록, Telegram 알림을 자동화하는 Python 프로젝트입니다.

이 저장소는 실행 가능한 자동화 코드만 정리한 공개용 저장소입니다. 개인 실행 데이터, 인증 정보, 로컬 로그, 과거 작업 문서는 포함하지 않습니다.

## 주요 기능

- Lotto 6/45 자동화 실행
- 연금복권 720+ 자동화 실행
- 당첨 결과 파싱
- Google Sheets 결과 기록
- Telegram 성공/실패 알림
- 예약 실행을 위한 n8n 워크플로 템플릿
- 복권 결과 파싱과 당첨 로직 테스트

## 프로젝트 구조

```text
config/
  n8n_lotto645_workflow.json
  n8n_pension720_workflow.json
scripts/
  google_sheets.py
  lotto645_runner.py
  pension720_runner.py
  test_runner.py
tests/
  test_lotto645.py
  test_pension720.py
data/
logs/
requirements.txt
```

## 설치

Python 의존성을 설치합니다.

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
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

실제 계정 정보, Telegram 토큰, Google 인증 파일은 GitHub에 커밋하지 마세요.

## 수동 실행

브라우저 자동화 없이 흐름만 확인하려면 dry-run으로 실행합니다.

```bash
python3 scripts/lotto645_runner.py --dry-run
python3 scripts/pension720_runner.py --dry-run
```

실제 자동화를 실행합니다.

```bash
python3 scripts/lotto645_runner.py
python3 scripts/pension720_runner.py
```

n8n 명령 파이프라인만 간단히 확인하려면 다음 명령을 사용합니다.

```bash
python3 scripts/test_runner.py
python3 scripts/test_runner.py --fail
```

## 테스트

```bash
python3 -m pytest tests/
```

## n8n 예약 실행

n8n Code 노드에서 로컬 명령과 환경 변수에 접근할 수 있도록 실행합니다.

```bash
NODE_FUNCTION_ALLOW_BUILTIN=child_process N8N_BLOCK_ENV_ACCESS_IN_NODE=false npx n8n
```

n8n에서 아래 워크플로 템플릿을 import합니다.

- `config/n8n_lotto645_workflow.json`
- `config/n8n_pension720_workflow.json`

워크플로를 실행하기 전에 `LOTTERY_AUTO_ROOT`를 이 저장소의 절대 경로로 설정합니다.

```bash
export LOTTERY_AUTO_ROOT="<repo-path>/lottery-pension-auto"
```

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

### 실패 알림

예외 발생 시 실행 시각과 에러 메시지를 보냅니다.

```text
[FAIL] lotto645 automation failed

Run time: 2026-06-16 10:00

Error: <에러 메시지>
```

## 커밋하지 않는 파일

아래 파일은 개인 실행 정보나 인증 정보를 포함할 수 있으므로 저장소에 커밋하지 않습니다.

- `config/service_account.json`
- `config/credentials.json`
- `config/token.json`
- `.env`
- `data/*.json`
- `logs/`
- 스크린샷과 디버그 로그

## 주의사항

- 실제 구매 자동화는 계정, 결제, 사이트 정책과 관련될 수 있으므로 사용 전 정책과 책임 범위를 확인하세요.
- 공개 저장소에는 API key, 비밀번호, Telegram Bot Token, Chat ID, Google 서비스 계정 JSON을 올리지 마세요.
- 먼저 `--dry-run`과 테스트로 동작을 확인한 뒤 실제 실행하세요.
