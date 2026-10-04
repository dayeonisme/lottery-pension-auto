#!/usr/bin/env bash
# 내 PC(gcloud, 서버 프로젝트 계정으로 로그인)에서 실행.
# 서버 프로젝트에 Sheets용 서비스 계정을 만들고 키 파일을 발급한다.
# Usage: PROJECT_ID=<프로젝트ID> scripts/gcp_service_account.sh [SA_NAME]
# 키 파일은 저장소 밖(~/lottery_sa_key.json)에 저장된다. 절대 커밋/채팅에 붙여넣지 말 것.
set -euo pipefail

: "${PROJECT_ID:?PROJECT_ID 환경변수 필요}"
SA_NAME="${1:-lottery-sheets}"
SA_EMAIL="$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com"
KEY_PATH="$HOME/lottery_sa_key.json"

echo "project=$PROJECT_ID  service_account=$SA_EMAIL  key=$KEY_PATH"
read -r -p "계속? [y/N] " ans
[[ "$ans" == "y" ]] || exit 1

gcloud services enable sheets.googleapis.com drive.googleapis.com --project "$PROJECT_ID"

gcloud iam service-accounts describe "$SA_EMAIL" --project "$PROJECT_ID" >/dev/null 2>&1 \
  || gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT_ID" \
       --display-name "lottery auto Google Sheets"

[[ -e "$KEY_PATH" ]] && { echo "$KEY_PATH 이미 존재 — 덮어쓰지 않음. 옮기거나 삭제 후 재실행"; exit 1; }
(umask 077; gcloud iam service-accounts keys create "$KEY_PATH" --iam-account "$SA_EMAIL" --project "$PROJECT_ID")

echo
echo "== 완료 =="
echo "1) 구글 시트 '공유'에 아래 이메일을 '편집자'로 추가:"
echo "   $SA_EMAIL"
echo "2) 키 파일을 서버로 업로드: $KEY_PATH"
