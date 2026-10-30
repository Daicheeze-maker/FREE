"""WSGI entry point: `gunicorn wsgi:app` (Linux) or `python serve.py` (Windows/any)."""
from velora import create_app

app = create_app()
