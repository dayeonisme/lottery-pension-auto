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

# n8n CLI는 실행 중인 서비스와 같은 유저/홈(DB, 암호화 키 위치)으로 실행해야 한다.
# (root로 실행하면 /root/.n8n 에 별도 DB가 새로 생겨 실제 n8n에 반영되지 않는다.)
N8N_USER="$(systemctl show -p User --value n8n)"
[[ -n "$N8N_USER" ]] || { echo "n8n 서비스 User 를 찾지 못함 — 중단"; exit 1; }
N8N_HOME="$(getent passwd "$N8N_USER" | cut -d: -f6)"
N8N_BIN="$(sudo -u "$N8N_USER" bash -lc 'command -v n8n' || true)"
[[ -n "$N8N_BIN" ]] || N8N_BIN="$(systemctl show -p ExecStart --value n8n | grep -o 'path=[^ ;]*' | head -1 | cut -d= -f2)"
echo "n8n user=$N8N_USER home=$N8N_HOME bin=$N8N_BIN"
# n8n CLI가 현재 디렉터리를 스캔하므로 서비스 유저가 읽을 수 있는 곳으로 이동(EACCES 방지)
cd "$N8N_HOME"
n8n_cli() { sudo -u "$N8N_USER" env HOME="$N8N_HOME" $(sudo cat "$ENV_FILE" | xargs) "$N8N_BIN" "$@"; }

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
