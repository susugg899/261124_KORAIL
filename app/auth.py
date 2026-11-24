from flask import Blueprint, flash, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user  # noqa: F401

from .extensions import db, login_manager
from .models import User

bp = Blueprint("auth", __name__)

PUBLIC_ENDPOINTS = {"auth.login", "static"}


def init_auth(app):
    login_manager.session_protection = "strong"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    @login_manager.unauthorized_handler
    def unauthorized():
        if request.path.startswith("/api/"):
            return jsonify(ok=False, error="로그인이 필요합니다."), 401
        return redirect(url_for("auth.login", next=request.full_path.rstrip("?")))

    @app.before_request
    def require_login():
        """F-12: 로그인하지 않으면 로그인 화면 외 모든 화면 접근을 막는다."""
        if request.endpoint is None or request.endpoint in PUBLIC_ENDPOINTS:
            return None
        if not current_user.is_authenticated:
            return login_manager.unauthorized()
        return None


def _safe_next(target):
    return bool(target) and target.startswith("/") and not target.startswith("//") and "\\" not in target


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("employees.list_"))
    error = None
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        password = request.form.get("password") or ""
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            target = request.args.get("next")
            return redirect(target if _safe_next(target) else url_for("employees.list_"))
        error = "아이디 또는 비밀번호가 올바르지 않습니다."
    has_admin = User.query.first() is not None
    return render_template("login.html", error=error, has_admin=has_admin), (401 if error else 200)


@bp.route("/logout")
def logout():
    logout_user()
    flash("로그아웃했습니다.", "info")
    return redirect(url_for("auth.login"))
