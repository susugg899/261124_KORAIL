import os
import secrets
import warnings


ON_VERCEL = bool(os.environ.get("VERCEL"))


def normalize_db_url(url):
    """Postgres URL을 순수 Python 드라이버(pg8000)용으로 바꾼다.

    pg8000은 컴파일된 확장(DLL)이 없어 Windows 애플리케이션 제어 정책에 막히지 않고,
    Vercel(Linux)에서도 그대로 동작한다. pg8000은 ?sslmode= 같은 쿼리 옵션을 받지 않으므로 제거한다.
    """
    if not url:
        return url
    for prefix in ("postgres://", "postgresql://", "postgresql+psycopg2://"):
        if url.startswith(prefix):
            url = "postgresql+pg8000://" + url[len(prefix):]
            break
    if url.startswith("postgresql+pg8000://"):
        url = url.split("?", 1)[0]
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    # 로컬: 상대 경로 sqlite URI(sqlite:///card.db)는 Flask-SQLAlchemy가 instance/ 폴더 기준으로 해석한다.
    #       값이 없으면 create_app()에서 instance/card.db로 지정한다.
    # 배포: Supabase Postgres 연결 문자열 (postgresql://...)
    SQLALCHEMY_DATABASE_URI = normalize_db_url(os.environ.get("DATABASE_URL"))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024  # CSV 업로드 2MB 제한
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = ON_VERCEL  # 배포(HTTPS)에서만 Secure 쿠키
    WTF_CSRF_TIME_LIMIT = None  # 세션이 살아 있는 동안 토큰 유효
    PER_PAGE = 20


def ensure_secret_key(app):
    if not app.config.get("SECRET_KEY"):
        if ON_VERCEL:
            raise RuntimeError("SECRET_KEY 환경변수가 없습니다. Vercel 프로젝트 환경변수에 설정해 주세요.")
        warnings.warn(
            "SECRET_KEY가 설정되지 않아 임시 키를 사용합니다. .env 파일을 만들어 주세요. "
            "(앱을 다시 켜면 로그인이 풀립니다)"
        )
        app.config["SECRET_KEY"] = secrets.token_hex(32)


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
