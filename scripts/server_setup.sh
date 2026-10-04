#!/usr/bin/env bash
# GCP 서버(브라우저 SSH)에서 실행: 코드 pull → n8n 환경변수 → 워크플로 import → 재시작.
# Usage: scripts/server_setup.sh <서버외부IP>
# 월간 결산 워크플로는 dry-run 확인 전이라 활성화하지 않는다.
set -euo pipefail

IP="${1:?서버 외부 IP 필요}"
REPO=/home/ubuntu/lottery_auto
ENV_FILE=/etc/n8n/env

sudo -u ubuntu git -C "$REPO" pull --ff-only

grep -q '^WEBHOOK_URL=' <(sudo cat "$ENV_FILE") \
  || echo "WEBHOOK_URL=http://$IP:5678/" | sudo tee -a "$ENV_FILE" >/dev/null

# n8n CLI는 서비스와 같은 환경변수(DB/암호화 키 위치)로 실행해야 한다.
n8n_cli() { sudo env $(sudo cat "$ENV_FILE" | xargs) n8n "$@"; }

# 배포 토큰: 신규 생성하여 credential 로 import (토큰은 한 번만 출력)
TOKEN="$(openssl rand -hex 32)"
CRED_TMP="$(mktemp)"; trap 'rm -f "$CRED_TMP"' EXIT
cat > "$CRED_TMP" <<JSON
[{"id":"deploytoken01","name":"deploy-token","type":"httpHeaderAuth",
  "data":{"name":"X-Deploy-Token","value":"$TOKEN"}}]
JSON
n8n_cli import:credentials --input="$CRED_TMP"

n8n_cli import:workflow --input="$REPO/config/n8n_deploy_workflow.json"
n8n_cli import:workflow --input="$REPO/config/n8n_monthly_report_workflow.json"

DEPLOY_ID="$(n8n_cli list:workflow | awk -F'|' '$2=="deploy lottery_auto"{print $1}' | head -1)"
[[ -n "$DEPLOY_ID" ]] && n8n_cli update:workflow --id="$DEPLOY_ID" --active=true

sudo systemctl restart n8n
echo
echo "== 완료. 배포 토큰(지금 한 번만 표시, 비밀번호 관리자에 저장) =="
echo "$TOKEN"
echo "호출: curl -X POST http://$IP:5678/webhook/deploy-lottery-auto -H \"X-Deploy-Token: <토큰>\""
