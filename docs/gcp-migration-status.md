# GCP 마이그레이션 진행 상태

**작성일**: 2026-04-04  
**서버 IP**: <your-gcp-ip>  
**n8n 웹 UI**: http://<your-gcp-ip>:5678

---

## 완료

### 버그 수정
- **로그인 체크 셀렉터 수정** (`pension720_runner.py`, `lotto645_runner.py`)
  - 동행복권 사이트 개편으로 로그인 후 "간소화페이지" 노출 → 로그아웃 버튼 없음
  - 기존: `document.querySelector('#gnb_logout, ...')` → 변경: `'/login' not in page.url`

- **연금복권 구매 확인 팝업 처리** (`pension720_runner.py`)
  - `a.lotto720_btn_pay` 클릭 후 인페이지 팝업(`#lotto720_popup_confirm`)이 열리는데 최종 구매 버튼을 안 눌러서 실제 구매가 안 됐음
  - 팝업 visible 대기 → `#lotto720_popup_confirm a.btn_blue` 클릭 → 구매완료 팝업 대기 추가

- **Playwright Chromium 메모리 최적화 플래그 추가** (GCP e2-micro 대응)
  - `--no-sandbox`, `--disable-dev-shm-usage`, `--disable-gpu`, `--disable-software-rasterizer`, `--disable-extensions`

### GCP 서버 구축
| 항목 | 값 |
|------|-----|
| 머신 타입 | e2-micro |
| OS | Ubuntu 22.04 LTS |
| 리전/존 | <ZONE> |
| Static IP | <your-gcp-ip> |
| Swap | 2GB |
| Node.js | 20.x |
| Python | 3.10 |

### n8n 설정
- systemd 서비스 등록: 재부팅 후 자동 시작, 크래시 시 자동 재시작
- 환경변수: `/etc/n8n/env` (DHLOTTERY_ID/PW, TELEGRAM, N8N 설정, `GENERIC_TIMEZONE=Asia/Seoul`)
- 워크플로우 2개 임포트 및 활성화 (lotto645 automation, pension720 automation)

---

## 미완료 (추후 수정 예정)

### lotto645 STEP 1 당첨번호 조회 실패
- **원인**: 메인 페이지(`dhlottery.co.kr`)의 Swiper 캐러셀이 Linux headless 환경에서 초기화 안 됨
- **시도한 방법**:
  - `wait_for_selector('.lt645-inbox.swiper-slide-active')` 추가 → 타임아웃
  - `--single-process` 플래그 제거 → 동일 실패
  - JSON API(`common.do?method=getLottoNumber`) 사용 → 실패 (API 차단 추정)
- **권장 해결 방향**: 연금복권처럼 전용 결과 페이지(`gameResult.do?method=byWin`) 셀렉터 파악 후 수정
- **수정 시점**: 로또 구매 수량 리셋 시점에 진행 예정

### 로컬 Mac n8n 서비스 정리
- lotto645 수정 완료 후 진행
- `launchctl unload ~/Library/LaunchAgents/com.n8n.agent.plist`

---

## GCP 서버 접속 방법

```bash
# SSH 접속
gcloud compute ssh ubuntu@cinelog-vm --zone=<ZONE>

# dry-run 테스트
python3 scripts/pension720_runner.py --dry-run
python3 scripts/lotto645_runner.py --dry-run

# n8n 서비스 관리
sudo systemctl status n8n
sudo systemctl restart n8n
tail -f ~/lottery_auto/logs/n8n.log
```
