"""Vercel 진입점: Vercel Python 런타임이 이 파일의 `app`(WSGI)을 서버리스 함수로 실행한다."""
from app import create_app

app = create_app()
