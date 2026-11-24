import click
from sqlalchemy import text

from .extensions import db
from .models import (DEPARTMENT_DEFAULTS, POSITION_DEFAULTS, SETTING_DEFAULTS,
                     Department, Position, Setting, User)


def seed_initial_data():
    """초기 데이터(직급, 예시 부서, 회사 설정 기본값). 이미 있는 값은 건드리지 않는다."""
    if not Position.query.first():
        for i, name in enumerate(POSITION_DEFAULTS):
            db.session.add(Position(name=name, sort_order=i))
    if not Department.query.first():
        for i, name in enumerate(DEPARTMENT_DEFAULTS):
            db.session.add(Department(name=name, sort_order=i))
    for key, value in SETTING_DEFAULTS.items():
        if db.session.get(Setting, key) is None:
            db.session.add(Setting(key=key, value=value))
    db.session.commit()


def enable_rls():
    """Supabase(Postgres): public 스키마 테이블은 Supabase Data API(anon 키)로 노출된다.

    모든 테이블에 RLS를 켜고 정책은 만들지 않아 API로는 읽기·쓰기가 막히게 한다.
    앱은 postgres 역할로 직접 접속하므로 RLS의 영향을 받지 않는다.
    """
    if db.engine.dialect.name != "postgresql":
        return
    with db.engine.begin() as conn:
        for table in db.metadata.sorted_tables:
            conn.execute(text(f'ALTER TABLE public."{table.name}" ENABLE ROW LEVEL SECURITY'))
    click.echo(f"RLS 사용: {', '.join(t.name for t in db.metadata.sorted_tables)}")


def register_cli(app):
    @app.cli.command("init-db")
    def init_db():
        """테이블을 만들고 초기 데이터를 넣는다."""
        db.create_all()
        enable_rls()
        seed_initial_data()
        click.echo(f"DB 준비 완료: {db.engine.url.render_as_string(hide_password=True)}")

    @app.cli.command("create-admin")
    @click.option("--username", prompt="관리자 아이디", default="admin", show_default=True)
    @click.option("--password", prompt="비밀번호", hide_input=True, confirmation_prompt="비밀번호 확인")
    def create_admin(username, password):
        """관리자 계정을 만든다 (이미 있으면 비밀번호를 바꾼다)."""
        username = username.strip()
        if len(password) < 8:
            raise click.ClickException("비밀번호는 8자 이상이어야 합니다.")
        db.create_all()
        user = User.query.filter_by(username=username).first()
        if user:
            user.set_password(password)
            msg = f"'{username}' 비밀번호를 변경했습니다."
        else:
            user = User(username=username)
            user.set_password(password)
            db.session.add(user)
            msg = f"관리자 '{username}' 계정을 만들었습니다."
        db.session.commit()
        click.echo(msg)
