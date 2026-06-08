# GCP n8n 마이그레이션 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mac 로컬 n8n 자동화를 GCP e2-micro (Always Free) 서버로 이전하여 24/7 안정적 운영

**Architecture:** GCP e2-micro (Ubuntu 22.04, us-west1) 위에 n8n을 systemd 서비스로 실행. 2GB Swap + Playwright 메모리 최적화 플래그로 OOM 방지. 민감 파일(service_account.json, purchases JSON)은 scp로 직접 전송.

**Tech Stack:** gcloud CLI, GCP Compute Engine (e2-micro), Ubuntu 22.04, Node.js 18, n8n, Python 3.10, Playwright/Chromium, systemd

---

### Task 1: Playwright 메모리 최적화 플래그 추가 (로컬 코드 수정)

**Files:**
- Modify: `scripts/pension720_runner.py:341`
- Modify: `scripts/lotto645_runner.py:388`

- [ ] **Step 1: pension720_runner.py Chromium 실행 플래그 수정**

`scripts/pension720_runner.py` line 341을 다음으로 교체:

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

- [ ] **Step 2: lotto645_runner.py Chromium 실행 플래그 수정**

`scripts/lotto645_runner.py` line 388을 다음으로 교체:

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

- [ ] **Step 3: 커밋 및 푸시**

```bash
git add scripts/pension720_runner.py scripts/lotto645_runner.py
git commit -m "perf: Playwright Chromium 메모리 최적화 플래그 추가 (GCP e2-micro 대응)"
git push origin master
```

---

### Task 2: gcloud CLI 설치 및 인증 (로컬 Mac)

**Files:** 없음 (시스템 설치)

- [ ] **Step 1: gcloud CLI 설치**

```bash
brew install --cask google-cloud-sdk
```

설치 후 터미널 재시작 또는:
```bash
source "$(brew --prefix)/share/google-cloud-sdk/path.zsh.inc"
```

- [ ] **Step 2: 버전 확인**

```bash
gcloud --version
```

기대 출력 (버전은 다를 수 있음):
```
Google Cloud SDK 464.0.0
...
```

- [ ] **Step 3: GCP 계정 로그인**

```bash
gcloud auth login
```

브라우저가 열리면 GCP 계정으로 로그인.

- [ ] **Step 4: 프로젝트 설정**

GCP 콘솔(console.cloud.google.com)에서 프로젝트 ID 확인 후:

```bash
gcloud projects list
gcloud config set project [YOUR_PROJECT_ID]
```

- [ ] **Step 5: Compute Engine API 활성화**

```bash
gcloud services enable compute.googleapis.com
```

기대 출력:
```
Operation "operations/..." finished successfully.
```

---

### Task 3: GCP VM 생성

**Files:** 없음 (인프라 생성)

- [ ] **Step 1: Static IP 생성**

```bash
gcloud compute addresses create lottery-auto-ip \
  --region=us-west1
```

- [ ] **Step 2: 생성된 IP 확인**

```bash
gcloud compute addresses describe lottery-auto-ip --region=us-west1 --format='get(address)'
```

이 IP를 메모해둠 (이후 SSH 접속 및 n8n 웹 UI 접속에 사용).

- [ ] **Step 3: VM 생성**

```bash
gcloud compute instances create lottery-auto-server \
  --machine-type=e2-micro \
  --zone=us-west1-a \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=30GB \
  --boot-disk-type=pd-standard \
  --address=lottery-auto-ip \
  --tags=n8n-server \
  --metadata=enable-oslogin=false
```

기대 출력:
```
NAME                   ZONE        MACHINE_TYPE  ...  STATUS
lottery-auto-server    us-west1-a  e2-micro      ...  RUNNING
```

- [ ] **Step 4: 방화벽 규칙 추가 (n8n 포트 5678)**

```bash
gcloud compute firewall-rules create allow-n8n \
  --allow=tcp:5678 \
  --target-tags=n8n-server \
  --description="Allow n8n web UI access"
```

- [ ] **Step 5: SSH 접속 확인**

```bash
gcloud compute ssh ubuntu@lottery-auto-server --zone=us-west1-a
```

접속 성공 시 프롬프트: `ubuntu@lottery-auto-server:~$`

접속 후 `exit`로 나옴.

---

### Task 4: VM 기본 환경 설정

**아래 모든 스텝은 VM SSH 접속 후 실행:**

```bash
gcloud compute ssh ubuntu@lottery-auto-server --zone=us-west1-a
```

- [ ] **Step 1: 패키지 업데이트**

```bash
sudo apt update && sudo apt upgrade -y
```

- [ ] **Step 2: Python 3, pip, git 설치**

```bash
sudo apt install -y python3 python3-pip python3-venv git curl
```

확인:
```bash
python3 --version   # Python 3.10.x
pip3 --version      # pip 22.x
```

- [ ] **Step 3: 2GB Swap 설정**

```bash
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

부팅 시 자동 마운트 등록:
```bash
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

확인:
```bash
free -h
```

기대 출력 (Swap 행에 2G 표시):
```
              total        used        free
Mem:          975Mi        ...
Swap:         2.0Gi        0B          2.0Gi
```

- [ ] **Step 4: Node.js 18 설치**

```bash
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs
```

확인:
```bash
node --version   # v18.x.x
npm --version    # 9.x.x 또는 10.x.x
```

---

### Task 5: n8n 설치

**VM SSH 접속 상태에서 실행.**

- [ ] **Step 1: n8n 글로벌 설치**

```bash
sudo npm install -g n8n
```

설치 시간 약 2~3분 소요.

- [ ] **Step 2: 버전 확인**

```bash
n8n --version
```

기대 출력: `2.x.x`

---

### Task 6: 프로젝트 배포 및 Python 의존성 설치

**VM SSH 접속 상태에서 실행.**

- [ ] **Step 1: 프로젝트 clone**

```bash
cd ~
git clone https://github.com/dayeonisme/lottery_auto.git
cd lottery_auto
```

- [ ] **Step 2: Python 의존성 설치**

```bash
pip3 install -r requirements.txt
```

- [ ] **Step 3: Playwright 시스템 의존성 설치**

```bash
sudo python3 -m playwright install-deps chromium
```

- [ ] **Step 4: Playwright Chromium 설치**

```bash
python3 -m playwright install chromium
```

확인:
```bash
python3 -c "from playwright.sync_api import sync_playwright; print('OK')"
```

기대 출력: `OK`

- [ ] **Step 5: logs, data 디렉토리 확인**

```bash
mkdir -p ~/lottery_auto/logs ~/lottery_auto/data
```

---

### Task 7: 민감 파일 전송 (로컬 → VM)

**로컬 Mac 터미널에서 실행.**

- [ ] **Step 1: service_account.json 전송**

```bash
gcloud compute scp \
  <local-lottery-auto-root>/config/service_account.json \
  ubuntu@lottery-auto-server:/home/ubuntu/lottery_auto/config/service_account.json \
  --zone=us-west1-a
```

- [ ] **Step 2: data 파일 전송**

```bash
gcloud compute scp \
  <local-lottery-auto-root>/data/lotto645_purchases.json \
  <local-lottery-auto-root>/data/pension720_purchases.json \
  <local-lottery-auto-root>/data/last_run.json \
  ubuntu@lottery-auto-server:/home/ubuntu/lottery_auto/data/ \
  --zone=us-west1-a
```

- [ ] **Step 3: 전송 확인 (VM에서)**

```bash
gcloud compute ssh ubuntu@lottery-auto-server --zone=us-west1-a --command="ls ~/lottery_auto/config/ ~/lottery_auto/data/"
```

기대 출력에 `service_account.json`, `lotto645_purchases.json`, `pension720_purchases.json`, `last_run.json` 포함.

---

### Task 8: 환경변수 파일 생성 (VM)

**VM SSH 접속 상태에서 실행.**

- [ ] **Step 1: /etc/n8n 디렉토리 생성**

```bash
sudo mkdir -p /etc/n8n
```

- [ ] **Step 2: 환경변수 파일 생성**

```bash
sudo tee /etc/n8n/env > /dev/null << 'EOF'
DHLOTTERY_ID=ppplotto11
DHLOTTERY_PW=<dhlottery-password>
TELEGRAM_CHAT_ID=5806848967
TELEGRAM_BOT_TOKEN=<telegram-bot-token>
N8N_HOST=0.0.0.0
N8N_PORT=5678
N8N_PROTOCOL=http
GENERIC_TIMEZONE=Asia/Seoul
EOF
```

- [ ] **Step 3: 파일 권한 설정**

```bash
sudo chmod 600 /etc/n8n/env
sudo chown root:root /etc/n8n/env
```

---

### Task 9: n8n systemd 서비스 등록 (VM)

**VM SSH 접속 상태에서 실행.**

- [ ] **Step 1: systemd 서비스 파일 생성**

```bash
sudo tee /etc/systemd/system/n8n.service > /dev/null << 'EOF'
[Unit]
Description=n8n workflow automation
After=network.target

[Service]
Type=simple
User=ubuntu
EnvironmentFile=/etc/n8n/env
ExecStart=/usr/bin/n8n start
Restart=always
RestartSec=10
StandardOutput=append:/home/ubuntu/lottery_auto/logs/n8n.log
StandardError=append:/home/ubuntu/lottery_auto/logs/n8n_error.log

[Install]
WantedBy=multi-user.target
EOF
```

- [ ] **Step 2: n8n 경로 확인**

```bash
which n8n
```

기대 출력: `/usr/bin/n8n`  
다를 경우 위 ExecStart 경로를 수정.

- [ ] **Step 3: systemd 리로드 및 서비스 시작**

```bash
sudo systemctl daemon-reload
sudo systemctl enable n8n
sudo systemctl start n8n
```

- [ ] **Step 4: 서비스 상태 확인**

```bash
sudo systemctl status n8n
```

기대 출력:
```
● n8n.service - n8n workflow automation
     Loaded: loaded (/etc/systemd/system/n8n.service; enabled; ...)
     Active: active (running) since ...
```

- [ ] **Step 5: n8n 시작 대기 (약 15초)**

```bash
sleep 15 && curl -s http://localhost:5678/healthz
```

기대 출력: `{"status":"ok"}`

---

### Task 10: n8n 워크플로우 임포트 및 활성화 (VM)

**VM SSH 접속 상태에서 실행.**

- [ ] **Step 1: 워크플로우 JSON 경로 업데이트**

클론된 워크플로우 JSON의 Mac 경로를 VM 경로로 교체:

```bash
cd ~/lottery_auto

sed -i 's|<local-lottery-auto-root>|/home/ubuntu/lottery_auto|g' \
  config/n8n_lotto645_workflow.json \
  config/n8n_pension720_workflow.json
```

- [ ] **Step 2: 경로 교체 확인**

```bash
grep -c 'dayeon.park' config/n8n_lotto645_workflow.json config/n8n_pension720_workflow.json
```

기대 출력: 두 파일 모두 `0` (경로 없음)

- [ ] **Step 3: lotto645 워크플로우 임포트**

```bash
python3 -c "
import json, secrets, string
chars = string.ascii_letters + string.digits
data = json.load(open('config/n8n_lotto645_workflow.json'))
data['id'] = ''.join(secrets.choice(chars) for _ in range(16))
data['active'] = False
json.dump(data, open('/tmp/lotto645_import.json','w'), ensure_ascii=False, indent=2)
print('id:', data['id'])
"
n8n import:workflow --input=/tmp/lotto645_import.json
```

기대 출력:
```
Importing 1 workflows...
Successfully imported 1 workflow.
```

- [ ] **Step 4: pension720 워크플로우 임포트**

```bash
python3 -c "
import json, secrets, string
chars = string.ascii_letters + string.digits
data = json.load(open('config/n8n_pension720_workflow.json'))
data['id'] = ''.join(secrets.choice(chars) for _ in range(16))
data['active'] = False
json.dump(data, open('/tmp/pension720_import.json','w'), ensure_ascii=False, indent=2)
print('id:', data['id'])
"
n8n import:workflow --input=/tmp/pension720_import.json
```

- [ ] **Step 5: 두 워크플로우 활성화**

```bash
sqlite3 ~/.n8n/database.sqlite \
  "UPDATE workflow_entity SET active=1 WHERE name IN ('lotto645 automation', 'pension720 automation');"

sqlite3 ~/.n8n/database.sqlite \
  "SELECT name, active FROM workflow_entity;"
```

기대 출력:
```
lotto645 automation|1
pension720 automation|1
```

- [ ] **Step 6: n8n 서비스 재시작 (변경 반영)**

```bash
sudo systemctl restart n8n
sleep 15
sudo systemctl status n8n | grep Active
```

기대 출력: `Active: active (running)`

---

### Task 11: 검증

- [ ] **Step 1: n8n 웹 UI 접속 확인 (로컬 Mac 브라우저)**

브라우저에서: `http://[VM_STATIC_IP]:5678`

n8n 로그인 화면 또는 대시보드가 보이면 성공.

- [ ] **Step 2: pension720 dry-run 테스트 (VM)**

```bash
gcloud compute ssh ubuntu@lottery-auto-server --zone=us-west1-a
cd ~/lottery_auto
python3 scripts/pension720_runner.py --dry-run 2>&1
```

기대 출력 마지막 줄:
```
[DRY-RUN] STEP 3+4 skipped. Prize result: ...
```

- [ ] **Step 3: lotto645 dry-run 테스트 (VM)**

```bash
python3 scripts/lotto645_runner.py --dry-run 2>&1
```

기대 출력 마지막 줄:
```
[DRY-RUN] STEP 3+4 skipped. Prize result: ...
```

- [ ] **Step 4: 로그 확인**

```bash
tail -20 ~/lottery_auto/logs/pension720.log
tail -20 ~/lottery_auto/logs/lotto645.log
```

STEP 1, STEP 2 성공 로그 확인.

---

### Task 12: 로컬 Mac n8n 정리

- [ ] **Step 1: 로컬 n8n launchd 서비스 중지 및 해제**

```bash
launchctl unload ~/Library/LaunchAgents/com.n8n.agent.plist
```

- [ ] **Step 2: 서비스 중지 확인**

```bash
launchctl list | grep n8n
```

기대 출력: 아무것도 없음 (n8n 프로세스 없음)

- [ ] **Step 3: 완료 확인**

VM n8n 웹 UI(`http://[VM_IP]:5678`)에서 두 워크플로우가 active 상태인지 최종 확인.
