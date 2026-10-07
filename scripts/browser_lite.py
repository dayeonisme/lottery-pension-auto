"""
browser_lite.py
Playwright 메모리/트래픽 절감: 불필요한 리소스 요청을 차단한다.
- font/media: 모든 페이지에서 차단
- image: 조회 전용 페이지(www 메인/당첨결과)에서만 1x1 GIF로 대체.
  로그인/구매 페이지는 이미지형 버튼(<input type="image">)이 1x1이 되어 클릭이 안 되므로 그대로 둔다.
- CSS/JS/XHR: 그대로 (버튼 표시·사이트 JS 함수에 필요)
- 구매(STEP 3) 전에 remove_resource_blocking()으로 해제한다. route가 걸린 상태에서 로그인 직후
  (메인 페이지 로딩 중) el.dhlottery.co.kr로 이동하면 goto가 domcontentloaded에 도달하지 못하고
  30초 timeout 발생 (2026-10-05 로또 구매 실패, 서버에서 재현 확인).
BROWSER_LITE=0 이면 비활성화 (배포 없이 env로 롤백).
"""

import os
import base64
import logging
from urllib.parse import urlparse

_PIXEL_GIF = base64.b64decode('R0lGODlhAQABAIAAAAAAAP///yH5BAEAAAAALAAAAAABAAEAAAIBRAA7')
_ABORT_TYPES = {'font', 'media'}
_LOOKUP_HOST = 'www.dhlottery.co.kr'
_INTERACTIVE_PATHS = ('/login',)


def _is_lookup_page(request) -> bool:
    """요청을 일으킨 문서가 조회 전용 페이지인지 (로그인/구매 페이지가 아닌 www 페이지)."""
    try:
        doc = urlparse(request.frame.url)
    except Exception:
        return False
    return doc.hostname == _LOOKUP_HOST and not doc.path.startswith(_INTERACTIVE_PATHS)


def _handle(route):
    req = route.request
    if req.resource_type in _ABORT_TYPES:
        return route.abort()
    if req.resource_type == 'image' and _is_lookup_page(req):
        return route.fulfill(status=200, content_type='image/gif', body=_PIXEL_GIF)
    return route.continue_()


def apply_resource_blocking(context) -> None:
    if os.environ.get('BROWSER_LITE', '1') == '0':
        logging.info('BROWSER_LITE=0 — resource blocking disabled')
        return
    context.route('**/*', _handle)
    logging.info('Resource blocking enabled (font/media→abort, lookup-page image→1px)')


def remove_resource_blocking(context) -> None:
    context.unroute_all(behavior='ignoreErrors')
