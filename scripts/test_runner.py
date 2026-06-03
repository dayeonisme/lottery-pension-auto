#!/usr/bin/env python3
"""
test_runner.py
n8n 파이프라인 스모크 테스트용 스크립트. 브라우저/구매 없이 exit code만 반환.
Usage:
    python scripts/test_runner.py          # exit 0 (성공 시뮬레이션)
    python scripts/test_runner.py --fail   # exit 1 (실패 시뮬레이션)
"""

import sys

if '--fail' in sys.argv:
    print('{"exitCode": 1, "stderr": "test failure simulation"}', file=sys.stderr)
    sys.exit(1)
else:
    print('{"exitCode": 0}')
    sys.exit(0)
