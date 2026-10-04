#!/usr/bin/env bash
# 내 PC(gcloud 설치 + 서버 프로젝트 계정으로 로그인)에서 실행.
# n8n(5678)/SSH(22) 인그레스를 내 공인 IP로만 제한한다.
# Usage: PROJECT_ID=<프로젝트ID> scripts/gcp_firewall.sh [내IP]
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID 환경변수 필요}"
MY_IP="${1:-$(curl -s ifconfig.me | tr -d '%[:space:]')}"
IAP_RANGE="35.235.240.0/20"   # 콘솔 브라우저 SSH (잠금 방지용)

echo "project=$PROJECT_ID  my_ip=$MY_IP"
read -r -p "위 값으로 방화벽을 변경합니다. 계속? [y/N] " ans
[[ "$ans" == "y" ]] || exit 1

gcloud compute firewall-rules create allow-n8n-myip --project "$PROJECT_ID" \
  --direction=INGRESS --action=ALLOW --rules=tcp:5678 --source-ranges="$MY_IP/32" \
  || gcloud compute firewall-rules update allow-n8n-myip --project "$PROJECT_ID" \
       --source-ranges="$MY_IP/32"

# 브라우저 SSH가 되는 것을 확인한 뒤 SSH 제한 (소스에 IAP 대역 포함)
gcloud compute firewall-rules update default-allow-ssh --project "$PROJECT_ID" \
  --source-ranges="$MY_IP/32,$IAP_RANGE"

echo "남아있는 5678/22 규칙 (0.0.0.0/0 이 있으면 삭제/수정 필요):"
gcloud compute firewall-rules list --project "$PROJECT_ID" \
  --format="table(name,sourceRanges.list(),allowed[].map().firewall_rule().list())"
