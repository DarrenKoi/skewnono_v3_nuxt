"""복사용 가이드: 이미 실행 중인 Flask 앱에 FTP 프록시를 붙이는 방법.

서버 절반이며 인증 없음(신뢰하는 단일 사용자 — FTP_PROXY_TOKEN 미설정이라 모든
요청이 통과한다). 장비 FTP 서버에 닿을 수 있는 호스트에서 실행하며, 그 호스트에
FTP_PROXY_FTP_USER / FTP_PROXY_FTP_PASSWORD 환경 변수를 설정한다. 블루프린트를
등록하면 기존 앱에 다음 세 라우트가 추가된다:

    POST /download_sknn_v3     # 플릿 다운로드를 펼쳐 파일 바이트를 반환
    POST /list_dirs_sknn_v3    # 탐색 패스, 매칭되는 경로만 반환
    GET  /healthz_sknn_v3      # {"status": "ok"}

`_sknn_v3` 접미사는 앱이 이미 서비스하는 경로와 충돌하지 않게 해주므로, 당신 쪽에서
이름을 바꿀 것은 없다.

당신의 앱이 만들어지는 방식에 맞는 스니펫을 골라 붙여 넣으면 된다.
"""

from ftp_handler.proxy.flask_proxy import ftp_proxy_sknn_v3


# ── 경우 1: 앱 팩토리(create_app)가 있는 경우 ─────────────────────────────────
# 팩토리 안에 register_blueprint 한 줄만 추가하고, 평소처럼 반환한다.
def create_app():
    from flask import Flask

    app = Flask(__name__)

    # ... 기존 설정과 블루프린트들 ...

    app.register_blueprint(ftp_proxy_sknn_v3)  # <-- 추가하는 단 한 줄
    return app


# ── 경우 2: 모듈 수준에 `app = Flask(__name__)`가 있는 경우 ───────────────────
# 앱 객체가 생성되는 곳 옆에 이 한 줄을 넣으면 된다:
#
#     app.register_blueprint(ftp_proxy_sknn_v3)


# ── 재시작 후 확인 ────────────────────────────────────────────────────────────
# 서버가 다시 뜨면, 아래 요청이 {"status": "ok"}를 반환해야 한다:
#
#     curl http://localhost:8000/healthz_sknn_v3
#
# host_timeout 기본값은 45초(ADR 0001)이며, 60초짜리 워커 강제종료보다 먼저
# 발동하도록 정해졌다. WSGI 워커 타임아웃이 45초보다 짧으면 값을 키워라
# (gunicorn --timeout / uWSGI harakiri). 그러지 않으면 워커가 플릿 다운로드를
# 도중에 강제로 끊어버린다.
