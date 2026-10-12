"""
failure_diag.py
실패 진단 — 실패 시점의 화면/URL/응답 대기 중인 요청을 남겨 timeout 원인(대기열·빈 화면·리다이렉트 등)을 확정한다.
- track_pending_requests(page): 페이지 생성 직후 호출. 끝나지 않은 요청을 {url: 시작시각}으로 추적.
- capture_failure(...): logs/failure_{name}_*.png 저장 + URL·title·pending 요청 로그. 최신 keep개만 유지.
"""

import time
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

KST = timezone(timedelta(hours=9))


def track_pending_requests(page) -> dict:
    pending = {}
    page.on('request', lambda r: pending.__setitem__(r.url, time.time()))
    page.on('requestfinished', lambda r: pending.pop(r.url, None))
    page.on('requestfailed', lambda r: pending.pop(r.url, None))
    return pending


def prune_failure_screenshots(log_dir: Path, name: str, keep: int = 5) -> None:
    shots = sorted(log_dir.glob(f'failure_{name}_*.png'), key=lambda p: p.stat().st_mtime, reverse=True)
    for shot in shots[keep:]:
        shot.unlink(missing_ok=True)


def capture_failure(page, name: str, log_dir: Path, pending: dict = None, max_pending: int = 10) -> None:
    try:
        shot_path = log_dir / f'failure_{name}_{datetime.now(KST).strftime("%Y%m%d_%H%M%S")}.png'
        page.screenshot(path=str(shot_path))
        logging.error('Failure diagnostics: url=%s screenshot=%s', page.url, shot_path)
        logging.error('Failure diagnostics: title=%r', page.title())
    except Exception as e:
        logging.error('Failed to capture failure diagnostics: %r', e)
    if pending:
        now = time.time()
        oldest = sorted(pending.items(), key=lambda kv: kv[1])[:max_pending]
        logging.error('Failure diagnostics: %d pending requests (oldest %d):', len(pending), len(oldest))
        for url, started in oldest:
            logging.error('  pending %.1fs %s', now - started, url[:200])
    prune_failure_screenshots(log_dir, name)
