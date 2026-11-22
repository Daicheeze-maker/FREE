"""Authorization decorators, audit logging and small security helpers."""
from functools import wraps
from urllib.parse import urljoin, urlparse

from flask import abort, current_app, has_request_context, request
from flask_login import current_user

from .extensions import db
from .models import AuditLog


def roles_required(*roles):
    """Server-side role check. Roles live only in the database, never in client input."""
    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                from .extensions import login_manager
                return login_manager.unauthorized()
            if current_user.role not in roles:
                abort(403)
            return view(*args, **kwargs)
        return wrapped
    return decorator


def client_ip():
    if not has_request_context():
        return "start-up"  # run from the command line (start.bat / upgrade-demo), not from a web page
    return (request.remote_addr or "unknown")[:64]


def audit(action, target_type=None, target_id=None, details=None, actor=None, commit=False):
    actor_id = None
    if actor is not None:
        actor_id = actor.id
    elif has_request_context() and current_user and current_user.is_authenticated:  # CLI/start-up: no one signed in
        actor_id = current_user.id
    db.session.add(AuditLog(
        actor_id=actor_id, action=action, target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=(details or "")[:800], ip_address=client_ip(),
    ))
    if commit:
        db.session.commit()


def is_safe_redirect(target):
    """Only allow redirects back to this host (prevents open redirects via ?next=)."""
    if not target:
        return False
    host = urlparse(request.host_url)
    dest = urlparse(urljoin(request.host_url, target))
    if not (dest.scheme in ("http", "https") and dest.netloc == host.netloc):
        return False
    try:  # only pages that exist: a stale ?next= must not land someone on a 404 after signing in
        current_app.url_map.bind(host.netloc).match(dest.path, method="GET")
    except Exception:
        return False
    return True


def apply_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault(
        "Content-Security-Policy",
        "default-src 'self'; img-src 'self' https: data:; script-src 'self'; "
        "style-src 'self' 'unsafe-inline'; font-src 'self'; connect-src 'self' https://nominatim.openstreetmap.org https://api.bigdatacloud.net; "
        "frame-ancestors 'none'; base-uri 'self'; form-action 'self'",
    )
    return response
