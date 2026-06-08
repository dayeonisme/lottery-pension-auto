# GCP n8n 마이그레이션 설계

**날짜**: 2026-04-04  
**목적**: Mac 로컬에서 실행 중인 n8n 자동화를 GCP e2-micro (Always Free) 서버로 이전하여 24/7 안정적 운영

---

## 1. 아키텍처

```
로컬 Mac
  └─ gcloud CLI
       ├─ VM 생성/관리
       └─ 민감 파일 scp 전송

GCP e2-micro (Ubuntu 22.04, us-west1)
  ├─ n8n (npm 설치, systemd 서비스로 상시 실행)
  │    ├─ Schedule Trigger: 매주 금요일 10:00 → pension720_runner.py
  │    └─ Schedule Trigger: 매주 일요일 10:00 → lotto645_runner.py
  ├─ Python 3.10 + Playwright + Chromium (headless)
  ├─ 2GB Swap (OOM 방지)
  └─ lottery_auto 프로젝트 (/home/ubuntu/lottery_auto)
```

---

## 2. GCP VM 스펙

| 항목 | 값 |
|------|-----|
| 머신 타입 | e2-micro |
| RAM | 1GB + 2GB Swap |
| CPU | 0.25 vCPU (burst) |
| OS | Ubuntu 22.04 LTS |
| 리전 | us-west1 (Always Free 해당 리전) |
| 스토리지 | 30GB HDD (Always Free 한도) |
| 외부 IP | 고정 IP (Static) |
| 비용 | $0/월 (Always Free 조건 충족 시) |

> **Always Free 조건**: us-west1 / us-central1 / us-east1 중 하나, e2-micro 1대, 30GB HDD 이하

---

## 3. 메모리 사용량 추산

| 상태 | OS | n8n | Python+Playwright | 합계 |
|------|-----|-----|-------------------|------|
| 평상시 | 150MB | 300MB | - | 450MB |
| 스크립트 실행 중 | 150MB | 300MB | 480MB | 930MB |

- RAM 1GB 초과분(~70MB)을 Swap이 커버
- Playwright 메모리 최적화 플래그 적용 시 실행 중 ~780MB로 감소

---

## 4. Playwright 메모리 최적화

`pension720_runner.py`, `lotto645_runner.py`의 Chromium 실행 시 아래 플래그 추가:

```python
browser = p.chromium.launch(
    headless=True,
    args=[
        '--no-sandbox',
        '--disable-dev-shm-usage',
        '--disable-gpu',
        '--disable-software-rasterizer',
        '--disable-extensions',
        '--single-process',
    ]
)
```

---

## 5. 파일 구성

### GitHub에 있는 파일 (git clone으로 배포)
- `scripts/` — 모든 Python 스크립트
- `requirements.txt`
- `config/n8n_*.json` — n8n 워크플로우

### scp로 직접 전송하는 민감 파일
- `config/service_account.json` — Google Sheets 서비스 계정 키
- `data/lotto645_purchases.json` — 로또 구매 내역
- `data/pension720_purchases.json` — 연금복권 구매 내역
- `data/last_run.json` — 마지막 실행 상태

---

## 6. 환경변수

n8n systemd 서비스의 `EnvironmentFile`로 관리:

```
/etc/n8n/env
```

```
DHLOTTERY_ID=<dhlottery-id>
DHLOTTERY_PW=<dhlottery-password>
TELEGRAM_CHAT_ID=<telegram-chat-id>
TELEGRAM_BOT_TOKEN=<telegram-bot-token>
```

파일 권한: `chmod 600 /etc/n8n/env`

---

## 7. n8n 워크플로우

기존 `config/n8n_lotto645_workflow.json`, `config/n8n_pension720_workflow.json`을 그대로 임포트.  
Python 실행 경로만 VM 환경에 맞게 수정:

- 기존: `/usr/bin/python3 <local-existing-service-root>/scripts/...`
- 변경: `/usr/bin/python3 /home/ubuntu/lottery_auto/scripts/...`

---

## 8. 배포 순서

1. **로컬**: gcloud CLI 설치 및 `gcloud auth login`
2. **로컬**: GCP VM 생성 (gcloud compute instances create)
3. **VM**: apt 업데이트, Python 3, pip 설치
4. **VM**: 2GB Swap 설정
5. **VM**: npm + n8n 설치
6. **VM**: git clone lottery_auto
7. **VM**: pip install -r requirements.txt && playwright install chromium
8. **VM**: Playwright 의존 시스템 패키지 설치 (playwright install-deps)
9. **로컬→VM**: scp로 민감 파일 전송
10. **VM**: /etc/n8n/env 환경변수 파일 생성
11. **VM**: n8n systemd 서비스 등록 및 시작
12. **VM**: n8n 워크플로우 임포트 및 활성화
13. **검증**: n8n 웹 UI 접속 확인, dry-run 테스트

---

## 9. 로컬 Mac n8n 정리 (마이그레이션 완료 후)

- `launchctl unload ~/Library/LaunchAgents/com.n8n.agent.plist`
- 로컬 n8n은 선택적으로 유지 가능 (백업 용도)
