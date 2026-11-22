"""Selling is by application: a buyer applies, an admin approves or rejects.

Approval creates (or switches back on) the buyer's linked seller profile (their email + SELLER_SUFFIX).
"""
import secrets

from ..extensions import db
from ..models import (APP_APPROVED, APP_PENDING, APP_REJECTED, ROLE_CUSTOMER, ROLE_SELLER, SELLER_SUFFIX,
                      SellerApplication, User, utcnow)
from ..security import audit
from .orders import notify


def seller_profile_of(buyer, include_off=False):
    q = User.query.filter_by(email=buyer.email + SELLER_SUFFIX, role=ROLE_SELLER)
    return q.first() if include_off else q.filter_by(is_active_account=True).first()


def latest_application(buyer):
    return (SellerApplication.query.filter_by(user_id=buyer.id)
            .order_by(SellerApplication.created_at.desc(), SellerApplication.id.desc()).first())


def pending_count():
    return SellerApplication.query.filter_by(status=APP_PENDING).count()


def apply(buyer, shop_name, phone, about):
    """Returns the new application. Raises ValueError if they are already a seller or already waiting."""
    if buyer.role != ROLE_CUSTOMER:
        raise ValueError("Only buyer accounts can apply to sell.")
    if seller_profile_of(buyer):
        raise ValueError("You're already a seller.")
    last = latest_application(buyer)
    if last is not None and last.status == APP_PENDING:
        raise ValueError("Your application is already waiting for the admin.")
    app = SellerApplication(user_id=buyer.id, shop_name=shop_name, phone=phone, about=about)
    db.session.add(app)
    db.session.flush()
    audit("seller.apply", "seller_application", app.id, f"{buyer.email} applied to sell as “{shop_name}”", actor=buyer)
    for admin in User.query.filter_by(role="admin", is_active_account=True):
        notify(admin.id, "New seller application", f"{buyer.full_name} wants to sell as “{shop_name}”.",
               "/admin/seller-requests", icon="store")
    return app


def approve(app, admin):
    if app.status != APP_PENDING:
        raise ValueError("This application was already decided.")
    buyer = app.user
    seller = seller_profile_of(buyer, include_off=True)
    if seller is None:
        seller = User(email=buyer.email + SELLER_SUFFIX, full_name=app.shop_name, role=ROLE_SELLER, phone=app.phone)
        seller.set_password(secrets.token_urlsafe(24))  # signed into through the buyer account, never directly
        db.session.add(seller)
    else:
        seller.is_active_account = True
        seller.full_name = app.shop_name
    app.status, app.reviewed_at, app.reviewed_by_id = APP_APPROVED, utcnow(), admin.id
    audit("seller.approve", "seller_application", app.id, f"Approved {buyer.email} as “{app.shop_name}”", actor=admin)
    notify(buyer.id, "You're now a seller!", f"Your shop “{app.shop_name}” was approved. Open the account menu and choose "
           "Switch to seller profile to start.", "/account/sell", icon="store")
    return seller


def reject(app, admin, note):
    if app.status != APP_PENDING:
        raise ValueError("This application was already decided.")
    app.status, app.reviewed_at, app.reviewed_by_id = APP_REJECTED, utcnow(), admin.id
    app.admin_note = (note or "").strip()[:300] or None
    audit("seller.reject", "seller_application", app.id, f"Rejected {app.user.email}: {app.admin_note or 'no reason given'}",
          actor=admin)
    notify(app.user.id, "Your seller application wasn't approved",
           app.admin_note or "You can update your details and apply again.", "/account/sell", icon="store")


def revoke(seller, admin):
    """Switch a seller profile off (the buyer account keeps working)."""
    seller.is_active_account = False
    audit("seller.revoke", "user", seller.id, f"Seller access removed: {seller.email}", actor=admin)
    buyer = User.query.filter_by(email=seller.email.removesuffix(SELLER_SUFFIX), role=ROLE_CUSTOMER).first()
    if buyer is not None:
        notify(buyer.id, "Your seller access was removed", "Contact the store if you think this is a mistake.",
               "/account/sell", icon="store")


def review_legacy_sellers():
    """Older versions gave every buyer a seller profile automatically. Selling now needs the admin's approval
    (like Lazada or Shopee), so such a profile is switched off and sent to Admin -> Seller requests as a pending
    application. Approving it switches the same profile (and its shop name) back on. Returns the buyer emails."""
    moved = []
    for seller in User.query.filter(User.role == ROLE_SELLER, User.is_active_account.is_(True),
                                    User.email.like(f"%{SELLER_SUFFIX}")).all():
        buyer = User.query.filter_by(email=seller.email.removesuffix(SELLER_SUFFIX), role=ROLE_CUSTOMER).first()
        if buyer is None:
            continue
        if SellerApplication.query.filter_by(user_id=buyer.id, status=APP_APPROVED).first():
            continue  # approved by an admin: a real seller
        seller.is_active_account = False
        if not SellerApplication.query.filter_by(user_id=buyer.id, status=APP_PENDING).first():
            db.session.add(SellerApplication(
                user_id=buyer.id, shop_name=(seller.full_name or buyer.full_name or "My shop")[:80],
                phone=seller.phone or buyer.phone or "Not given",
                about="Seller profile from an earlier version of the store, made automatically. Approve to let them keep selling."))
        notify(buyer.id, "Your seller profile is waiting for approval",
               "Selling now needs the admin's approval. Your request was sent automatically.", "/account/sell", icon="store")
        audit("seller.legacy_review", "user", seller.id, f"Automatic seller profile sent for approval: {seller.email}", actor=None)
        moved.append(buyer.email)
    db.session.commit()
    return moved
