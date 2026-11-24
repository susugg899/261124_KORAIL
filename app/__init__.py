import os

from dotenv import load_dotenv

# config.py가 import 시점에 환경변수를 읽으므로 그 전에 .env를 불러온다.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from flask import Flask, jsonify, render_template, request  # noqa: E402
from flask_wtf.csrf import CSRFError  # noqa: E402

from .config import Config, ensure_secret_key  # noqa: E402
from .extensions import csrf, db, login_manager  # noqa: E402
from .validators import format_phone  # noqa: E402


def create_app(config_class=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_class or Config)
    ensure_secret_key(app)

    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass  # Vercel 등 읽기 전용 파일 시스템 (DB는 Postgres를 쓴다)
    if not app.config.get("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///" + os.path.join(app.instance_path, "card.db")
    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql+pg8000://"):
        import ssl

        from sqlalchemy.pool import NullPool
        # TLS 암호화는 항상 쓰고, 인증서 체인 검증은 생략한다 (libpq의 sslmode=require와 같은 수준).
        # Supabase는 자체 루트 CA를 쓰므로 기본 검증은 실패한다. 더 엄격하게 하려면
        # 대시보드에서 받은 CA 파일 경로를 DB_SSL_ROOT_CERT에 지정한다 (verify-full).
        ca_file = os.environ.get("DB_SSL_ROOT_CERT")
        if ca_file:
            ssl_ctx = ssl.create_default_context(cafile=ca_file)
        else:
            ssl_ctx = ssl.create_default_context()
            ssl_ctx.check_hostname = False
            ssl_ctx.verify_mode = ssl.CERT_NONE
        # 서버리스 함수는 요청마다 새로 뜰 수 있으므로 연결을 들고 있지 않는다 (Supabase 풀러가 관리).
        app.config.setdefault("SQLALCHEMY_ENGINE_OPTIONS", {
            "poolclass": NullPool,
            "connect_args": {"ssl_context": ssl_ctx},
        })

    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    from . import models  # noqa: F401  (모델 등록)
    from .auth import bp as auth_bp, init_auth
    from .views.admin import bp as admin_bp
    from .views.bulk import bp as bulk_bp
    from .views.cards import bp as cards_bp
    from .views.employees import bp as employees_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(employees_bp)
    app.register_blueprint(cards_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(bulk_bp)
    init_auth(app)

    from .cli import register_cli
    register_cli(app)

    @app.context_processor
    def inject_settings():
        return {"settings": models.get_settings()}

    @app.template_filter("phone")
    def phone_filter(value):
        return format_phone(value) if value else ""

    @app.template_filter("dt")
    def dt_filter(value, fmt="%Y-%m-%d %H:%M"):
        return value.strftime(fmt) if value else ""

    def wants_json():
        return request.path.startswith("/api/")

    @app.errorhandler(404)
    def not_found(e):
        if wants_json():
            return jsonify(ok=False, error="대상을 찾을 수 없습니다."), 404
        return render_template("error.html", code=404, message="페이지를 찾을 수 없습니다."), 404

    @app.errorhandler(CSRFError)
    def csrf_error(e):
        if wants_json():
            return jsonify(ok=False, error="보안 토큰이 만료되었습니다. 페이지를 새로고침해 주세요."), 400
        return render_template("error.html", code=400,
                               message="보안 토큰이 만료되었습니다. 이전 페이지를 새로고침한 뒤 다시 시도해 주세요."), 400

    @app.errorhandler(413)
    def too_large(e):
        return render_template("error.html", code=413, message="파일이 너무 큽니다. (최대 2MB)"), 413

    return app
