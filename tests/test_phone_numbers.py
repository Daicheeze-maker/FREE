"""Mobile numbers are checked per country (libphonenumber rules) and saved in one standard form."""
import re

import pytest

from velora import phones
from velora.extensions import db
from velora.models import Address, Order

from .conftest import get_user, in_stock_product


@pytest.mark.parametrize("raw,country,expected", [
    ("09171234567", "PH", "+639171234567"),      # 11 digits with the leading 0
    ("9171234567", "PH", "+639171234567"),       # 10 digits after +63
    ("+63 917 123 4567", "PH", "+639171234567"),
    ("0917-123-4567", "PH", "+639171234567"),
    ("2025550142", "US", "+12025550142"),
    ("07400 123456", "GB", "+447400123456"),
    ("090-1234-5678", "JP", "+819012345678"),
    ("8123 4567", "SG", "+6581234567"),
    ("0412 345 678", "AU", "+61412345678"),
    ("06 12 34 56 78", "FR", "+33612345678"),
    ("612 34 56 78", "ES", "+34612345678"),
])
def test_valid_mobile_numbers_for_each_country(raw, country, expected):
    assert phones.normalize(raw, country) == expected


@pytest.mark.parametrize("raw,country,why", [
    ("0917123456", "PH", "10 digits"),            # one digit short
    ("091712345678", "PH", "10 digits"),          # one digit too many
    ("917123456789", "PH", "10 digits"),
    ("028123456", "PH", "10 digits"),             # a Manila landline, not a mobile
    ("+1 202 555 0142", "PH", "isn't from Philippines"),
    ("8123456", "SG", "8 digits"),
    ("02079460000", "GB", "mobile number"),       # London landline
    ("", "PH", "Enter a phone number"),
])
def test_wrong_numbers_are_refused_with_a_clear_reason(raw, country, why):
    with pytest.raises(ValueError) as exc:
        phones.normalize(raw, country)
    assert why in str(exc.value)


def test_every_display_currency_has_its_countries():
    codes = {c["code"] for c in phones.countries()}
    for currency, country in phones.CURRENCY_COUNTRY.items():
        assert country in codes, currency
    ph = phones.country_info("PH")
    assert (ph["dial"], ph["min"], ph["max"], ph["max_typed"]) == ("+63", 10, 10, 11)
    assert phones.country_info("SG")["max_typed"] == 8


def test_numbers_are_shown_nicely_and_old_ones_unchanged():
    assert phones.pretty("+639171234567") == "+63 917 123 4567"
    assert phones.pretty("call me maybe") == "call me maybe"
    assert phones.split("+639171234567") == ("PH", "9171234567")


def _token(client):
    page = client.get("/checkout").get_data(as_text=True)
    return re.search(r'checkout_token[^>]*value="([^"]+)"', page).group(1)


NEW = {"address_choice": "new", "addr-label": "Home", "addr-full_name": "Maya Santos", "addr-line1": "56 Kalayaan Ave",
       "addr-city": "Quezon City", "addr-region": "Metro Manila", "addr-postal_code": "1101", "addr-country": "Philippines",
       "addr-save_address": "y"}


def test_checkout_saves_the_number_in_standard_form(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    r = customer.post("/checkout", data={"checkout_token": _token(customer), **NEW,
                                         "addr-phone_country": "PH", "addr-phone": "0917 123 4567"})
    assert r.status_code == 302
    o = Order.query.order_by(Order.id.desc()).first()
    assert o.ship_phone == "+639171234567"
    assert "+63 917 123 4567" in customer.get(r.headers["Location"]).get_data(as_text=True)


def test_checkout_refuses_a_number_with_the_wrong_length(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    before = Order.query.count()
    r = customer.post("/checkout", data={"checkout_token": _token(customer), **NEW,
                                         "addr-phone_country": "PH", "addr-phone": "0917 123 456"})
    assert r.status_code == 400 and "mobile number has 10 digits after +63" in r.get_data(as_text=True)
    assert Order.query.count() == before
    r = customer.post("/checkout", data={"checkout_token": _token(customer), **NEW,
                                         "addr-phone_country": "XX", "addr-phone": "0917 123 4567"})
    assert r.status_code == 400  # a country that isn't offered


def test_forms_show_the_country_picker_with_limits(customer):
    customer.post(f"/cart/add/{in_stock_product().id}", data={"quantity": 1})
    for url in ("/checkout", "/account/addresses", "/account/profile"):
        page = customer.get(url).get_data(as_text=True)
        assert "data-phone-country" in page, url
        assert 'value="PH" data-dial="+63" data-max="11"' in page, url
        assert 'value="SG" data-dial="+65" data-max="8"' in page, url


def test_seller_application_uses_the_phone_picker(app):
    c = app.test_client()
    c.post("/account/register", data={"full_name": "New Seller", "email": "ns@example.com", "password": "Secret123",
                                      "confirm": "Secret123", "accept": "y"})
    assert "data-phone-country" in c.get("/account/sell").get_data(as_text=True)
    r = c.post("/account/sell", data={"shop_name": "NS Watches", "phone_country": "PH", "phone": "12345",
                                      "about": "Pre-owned automatic watches, serviced and tested.", "agree": "y"})
    assert r.status_code == 200 and "10 digits after +63" in r.get_data(as_text=True)
    c.post("/account/sell", data={"shop_name": "NS Watches", "phone_country": "PH", "phone": "09171234567",
                                  "about": "Pre-owned automatic watches, serviced and tested.", "agree": "y"})
    from velora.models import SellerApplication
    assert SellerApplication.query.one().phone == "+639171234567"


def test_editing_an_address_shows_country_and_digits_again(customer):
    u = get_user("buyer1@velora.example")
    a = Address.query.filter_by(user_id=u.id).first()
    a.phone = "+6581234567"
    db.session.commit()
    page = customer.get(f"/account/addresses/{a.id}/edit").get_data(as_text=True)
    assert 'value="81234567"' in page and re.search(r'value="SG"[^>]*selected', page)


def test_country_follows_the_display_currency(customer):
    customer.post("/currency", data={"currency": "SGD", "next": "/"})
    page = customer.get("/account/addresses").get_data(as_text=True)
    assert re.search(r'value="SG"[^>]*selected', page)


def test_profile_phone_is_optional_but_checked(customer):
    r = customer.post("/account/profile", data={"form": "profile", "full_name": "Maya Santos", "phone": "", "phone_country": "PH"})
    assert r.status_code == 302
    r = customer.post("/account/profile", data={"form": "profile", "full_name": "Maya Santos", "phone": "123", "phone_country": "PH"})
    assert r.status_code == 200 and "field__error" in r.get_data(as_text=True)
    customer.post("/account/profile", data={"form": "profile", "full_name": "Maya Santos", "phone": "09171234567", "phone_country": "PH"})
    db.session.expire_all()
    assert get_user("buyer1@velora.example").phone == "+639171234567"
