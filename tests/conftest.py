import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app  # noqa: E402
from app.cli import seed_initial_data  # noqa: E402
from app.config import TestConfig  # noqa: E402
from app.extensions import db  # noqa: E402
from app.models import User  # noqa: E402


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        seed_initial_data()
        user = User(username="admin")
        user.set_password("test-password")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def anon(app):
    return app.test_client()


@pytest.fixture
def client(app):
    c = app.test_client()
    res = c.post("/login", data={"username": "admin", "password": "test-password"})
    assert res.status_code == 302
    return c
