# lottery-pension-auto

Python automation for Lotto 6/45 and Pension Lottery 720+ purchases, prize checks, Google Sheets logging, and Telegram notifications.

This public repository is a clean copy of the runnable automation code. Private runtime data, credentials, local logs, and historical planning documents are intentionally excluded.

## Features

- Lotto 6/45 automation runner
- Pension Lottery 720+ automation runner
- Prize result parsing and Google Sheets updates
- Telegram success/failure notifications
- n8n workflow templates for scheduled execution
- Unit tests for lottery parsing and prize logic

## Project Structure

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

## Setup

Install dependencies:

```bash
pip3 install -r requirements.txt
python3 -m playwright install chromium
```

Create Google service account credentials:

1. Create a service account in Google Cloud Console.
2. Enable Google Sheets API and Google Drive API.
3. Save the downloaded JSON key as `config/service_account.json`.
4. Share the target spreadsheet with the service account email as an editor.

Set environment variables:

```bash
export GOOGLE_SPREADSHEET_ID="your_google_spreadsheet_id"
export GOOGLE_SERVICE_ACCOUNT_PATH="$PWD/config/service_account.json"
export DHLOTTERY_ID="your_dhlottery_id"
export DHLOTTERY_PW="your_dhlottery_password"
export TELEGRAM_CHAT_ID="your_telegram_chat_id"
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
```

## Manual Run

```bash
python3 scripts/lotto645_runner.py --dry-run
python3 scripts/pension720_runner.py --dry-run

python3 scripts/lotto645_runner.py
python3 scripts/pension720_runner.py
```

Smoke-test the n8n command pipeline without browser automation:

```bash
python3 scripts/test_runner.py
python3 scripts/test_runner.py --fail
```

Run tests:

```bash
python3 -m pytest tests/
```

## n8n

Start n8n with environment access enabled for Code nodes:

```bash
NODE_FUNCTION_ALLOW_BUILTIN=child_process N8N_BLOCK_ENV_ACCESS_IN_NODE=false npx n8n
```

Import the workflow templates:

- `config/n8n_lotto645_workflow.json`
- `config/n8n_pension720_workflow.json`

Set `LOTTERY_AUTO_ROOT` to the absolute path of this repository before running the workflows:

```bash
export LOTTERY_AUTO_ROOT="<repo-path>/lottery-pension-auto"
```

## Files Not Committed

The following files are private runtime artifacts and must not be committed:

- `config/service_account.json`
- `config/credentials.json`
- `config/token.json`
- `.env`
- `data/*.json`
- `logs/`
- screenshots and debug logs
