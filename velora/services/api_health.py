"""Bookkeeping for external API health (shown on the admin API health page)."""
from datetime import timedelta

from flask import current_app

from ..extensions import db
from ..models import ApiStatus, utcnow

OFF = "openfoodfacts"
FRANKFURTER = "frankfurter"


def _status(name):
    row = ApiStatus.query.filter_by(name=name).first()
    if row is None:
        row = ApiStatus(name=name)
        db.session.add(row)
    return row


def record_success(name, latency_ms=None):
    row = _status(name)
    row.last_success_at = utcnow()
    row.success_count = (row.success_count or 0) + 1
    row.last_latency_ms = latency_ms
    db.session.commit()


def record_error(name, message):
    row = _status(name)
    row.last_error_at = utcnow()
    row.last_error = str(message)[:500]
    row.error_count = (row.error_count or 0) + 1
    db.session.commit()


def in_backoff(name):
    """After a failure, don't hammer (or wait on) an unreachable API for a few minutes."""
    row = ApiStatus.query.filter_by(name=name).first()
    if not row or not row.last_error_at:
        return False
    if row.last_success_at and row.last_success_at > row.last_error_at:
        return False
    window = timedelta(minutes=current_app.config["API_RETRY_BACKOFF_MINUTES"])
    return utcnow() - row.last_error_at < window


def user_agent():
    cfg = current_app.config
    return f"VeloraMarket/1.0 ({cfg['CONTACT_EMAIL']})"
