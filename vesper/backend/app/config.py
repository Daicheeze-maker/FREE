import os
from pathlib import Path

# Minimal .env loader so the project needs no python-dotenv. Real env vars win.
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    for line in _env.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def env(name: str, default: str = "") -> str:
    # Read at call time so tests can monkeypatch the environment.
    return os.getenv(name, default)


MAX_SELLERS = 4
MAX_PRODUCTS_PER_SELLER = 5
SHIPPING_FEE_CENTAVOS = 18000  # flat demo rate: PHP 180.00
MAX_QTY_PER_LINE = 10
