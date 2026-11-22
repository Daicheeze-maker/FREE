"""Phone numbers per country, checked with Google's free libphonenumber rules (the `phonenumbers` package, works offline).

The store offers the countries of its display currencies. A number is stored in one standard form (E.164, e.g.
+639171234567) and shown nicely (+63 917 123 4567). Each country has its own digit limits: the Philippines takes
10 digits after +63 (or 11 when typed with the leading 0, e.g. 0917 123 4567). Mobile numbers only.
"""
from functools import lru_cache

import phonenumbers
from phonenumbers import NumberParseException, PhoneNumberFormat, PhoneNumberType

# (ISO code, name, flag) — the countries behind the store's display currencies
COUNTRIES = [
    ("PH", "Philippines", "🇵🇭"),      # PHP
    ("US", "United States", "🇺🇸"),    # USD
    ("GB", "United Kingdom", "🇬🇧"),   # GBP
    ("JP", "Japan", "🇯🇵"),            # JPY
    ("SG", "Singapore", "🇸🇬"),        # SGD
    ("AU", "Australia", "🇦🇺"),        # AUD
    ("DE", "Germany", "🇩🇪"),          # EUR
    ("FR", "France", "🇫🇷"),           # EUR
    ("IT", "Italy", "🇮🇹"),            # EUR
    ("ES", "Spain", "🇪🇸"),            # EUR
    ("NL", "Netherlands", "🇳🇱"),      # EUR
    ("IE", "Ireland", "🇮🇪"),          # EUR
]
CODES = [c[0] for c in COUNTRIES]
DEFAULT_COUNTRY = "PH"
CURRENCY_COUNTRY = {"PHP": "PH", "USD": "US", "GBP": "GB", "JPY": "JP", "SGD": "SG", "AUD": "AU", "EUR": "DE"}


@lru_cache(maxsize=None)
def country_info(code):
    """Dial code, digit limits and an example for one country, read from libphonenumber's metadata."""
    meta = phonenumbers.PhoneMetadata.metadata_for_region(code)
    # Mobile numbers only: they are what delivery updates go to (and they have strict, simple lengths)
    desc = meta.mobile if meta.mobile is not None and meta.mobile.possible_length else meta.general_desc
    lengths = {n for n in desc.possible_length if n > 0}
    example = phonenumbers.example_number_for_type(code, PhoneNumberType.MOBILE) or phonenumbers.example_number(code)
    trunk = meta.national_prefix or ""
    national = phonenumbers.format_number(example, PhoneNumberFormat.NATIONAL)
    return {
        "code": code,
        "name": dict((c[0], c[1]) for c in COUNTRIES)[code],
        "flag": dict((c[0], c[2]) for c in COUNTRIES)[code],
        "dial": f"+{meta.country_code}",
        "min": min(lengths),
        "max": max(lengths),
        "trunk": trunk,                                   # e.g. "0": people often type it first (0917…)
        "max_typed": max(lengths) + len(trunk),           # most digits allowed in the box
        "example": phonenumbers.format_number(example, PhoneNumberFormat.NATIONAL).lstrip(trunk).strip() if trunk else national,
    }


def countries():
    return [country_info(c) for c in CODES]


def normalize(raw, country):
    """Check a number for a country. Returns E.164 (+639171234567) or raises ValueError with a friendly message."""
    country = country if country in CODES else DEFAULT_COUNTRY
    info = country_info(country)
    raw = (raw or "").strip()
    digits = "".join(ch for ch in raw if ch.isdigit())
    if not digits:
        raise ValueError("Enter a phone number.")
    if not raw.startswith("+"):
        national = digits[len(info["trunk"]):] if info["trunk"] and digits.startswith(info["trunk"]) else digits
        if len(national) < info["min"] or len(national) > info["max"]:
            span = f"{info['min']}" if info["min"] == info["max"] else f"{info['min']} to {info['max']}"
            raise ValueError(f"A {info['name']} mobile number has {span} digits after {info['dial']}, like {info['example']}.")
    try:
        number = phonenumbers.parse(raw, country)
    except NumberParseException:
        raise ValueError(f"That doesn't look like a {info['name']} phone number, like {info['example']}.")
    if phonenumbers.region_code_for_number(number) != country:
        raise ValueError(f"That number isn't from {info['name']}. Pick its country first.")
    if not phonenumbers.is_valid_number(number):
        raise ValueError(f"That isn't a valid {info['name']} mobile number. Example: {info['dial']} {info['example']}.")
    if phonenumbers.number_type(number) not in (PhoneNumberType.MOBILE, PhoneNumberType.FIXED_LINE_OR_MOBILE):
        raise ValueError(f"Please enter a mobile number (for delivery updates), like {info['dial']} {info['example']}.")
    return phonenumbers.format_number(number, PhoneNumberFormat.E164)


def split(stored):
    """(country, national digits) for showing a stored number in the form again; (None, original) if it can't be read."""
    if not stored or not str(stored).startswith("+"):
        return None, stored or ""
    try:
        number = phonenumbers.parse(stored, None)
    except NumberParseException:
        return None, stored
    region = phonenumbers.region_code_for_number(number)
    if region not in CODES:
        return None, stored
    return region, str(number.national_number)


def pretty(stored):
    """+639171234567 -> +63 917 123 4567. Older free-text numbers are shown as they are."""
    if not stored:
        return ""
    try:
        number = phonenumbers.parse(stored, None if str(stored).startswith("+") else DEFAULT_COUNTRY)
        if phonenumbers.is_possible_number(number):
            return phonenumbers.format_number(number, PhoneNumberFormat.INTERNATIONAL)
    except NumberParseException:
        pass
    return stored
