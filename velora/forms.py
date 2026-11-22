from flask_wtf import FlaskForm
from flask_wtf.file import FileField
from wtforms import (BooleanField, DateTimeLocalField, EmailField, HiddenField, IntegerField,
                     PasswordField, RadioField, SelectField, StringField, TextAreaField)
from wtforms.validators import (DataRequired, Email, EqualTo, InputRequired, Length, NumberRange,
                                Optional, Regexp, ValidationError)

from . import phones
from .models import PRODUCT_STATUSES, ROLES
from .money import to_minor


def strip(value):
    return value.strip() if isinstance(value, str) else value


class PhoneFormMixin:
    """A `phone` box with a country picker. The number is checked for the chosen country (libphonenumber rules)
    and saved in one standard form, e.g. +639171234567."""
    phone_country = SelectField("Country", default=phones.DEFAULT_COUNTRY,
                                choices=[(c["code"], f"{c['flag']} {c['name']} ({c['dial']})") for c in phones.countries()])

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_submitted():
            if self.phone_country.data == phones.DEFAULT_COUNTRY:
                try:  # start on the country of the shopper's display currency
                    from flask import session
                    self.phone_country.data = phones.CURRENCY_COUNTRY.get(session.get("currency"), phones.DEFAULT_COUNTRY)
                except RuntimeError:
                    pass
            self.set_phone(self.phone.data)

    def set_phone(self, stored):
        """Show a saved number in the box as country + national digits."""
        region, national = phones.split(stored)
        if region:
            self.phone_country.data = region
        self.phone.data = national

    def validate_phone(self, field):
        if not field.data:
            return
        try:
            field.data = phones.normalize(field.data, self.phone_country.data)
        except ValueError as exc:
            raise ValidationError(str(exc))


class MoneyField(StringField):
    """Major-unit amount, validated and exposed as integer minor units via .minor"""
    minor = None

    def process_formdata(self, valuelist):
        super().process_formdata(valuelist)
        self.minor = None
        if self.data not in (None, ""):
            try:
                self.minor = to_minor(self.data)
            except ValueError as exc:
                raise ValueError(str(exc))


class PasswordStrength:
    def __call__(self, form, field):
        pw = field.data or ""
        if len(pw) < 8 or not any(c.isdigit() for c in pw) or not any(c.isalpha() for c in pw):
            raise ValidationError("Use at least 8 characters with letters and numbers.")


class LoginForm(FlaskForm):
    # No Email() check: any text signs in, and unknown ones become demo customers.
    email = EmailField("Email", validators=[DataRequired(), Length(max=255)], filters=[strip])
    password = PasswordField("Password", validators=[DataRequired(), Length(max=128)])
    remember = BooleanField("Keep me signed in")


class RegisterForm(FlaskForm):
    # Deliberately no role field: every self-registration is a customer.
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)], filters=[strip])
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)], filters=[strip])
    password = PasswordField("Password", validators=[DataRequired(), PasswordStrength(), Length(max=128)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])
    account_type = RadioField("I want to", choices=[("buyer", "Shop (buyer account)"), ("seller", "Shop and apply to sell")], default="buyer", validators=[Optional()])
    accept = BooleanField("I agree to the terms and privacy policy", validators=[DataRequired("Please accept to continue.")])


class SellerApplicationForm(PhoneFormMixin, FlaskForm):
    shop_name = StringField("Shop name", validators=[DataRequired(), Length(min=2, max=80)], filters=[strip])
    phone = StringField("Contact mobile number", validators=[DataRequired(), Length(max=40)], filters=[strip])
    about = TextAreaField("What will you sell?", validators=[DataRequired(), Length(min=20, max=1000, message="Tell the admin a little more (20 to 1,000 characters).")], filters=[strip])
    agree = BooleanField("I'll only sell genuine watches and follow the store's seller rules", validators=[DataRequired("Please agree to continue.")])


class SellerDecisionForm(FlaskForm):
    note = StringField("Note to the applicant (optional)", validators=[Optional(), Length(max=300)], filters=[strip])


class AdminSetupForm(FlaskForm):
    full_name = StringField("Your name", validators=[DataRequired(), Length(min=2, max=120)], filters=[strip])
    email = EmailField("Admin email", validators=[DataRequired(), Email(), Length(max=255)], filters=[strip])
    password = PasswordField("Password", validators=[DataRequired(), PasswordStrength(), Length(max=128)])
    confirm = PasswordField("Confirm password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])


class ProfileForm(PhoneFormMixin, FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)], filters=[strip])
    phone = StringField("Mobile number", validators=[Optional(), Length(max=40)], filters=[strip])


class PasswordChangeForm(FlaskForm):
    current = PasswordField("Current password", validators=[DataRequired()])
    password = PasswordField("New password", validators=[DataRequired(), PasswordStrength(), Length(max=128)])
    confirm = PasswordField("Confirm new password", validators=[DataRequired(), EqualTo("password", "Passwords must match.")])


class AddressForm(PhoneFormMixin, FlaskForm):
    label = StringField("Label", default="Home", validators=[DataRequired(), Length(max=40)], filters=[strip])
    full_name = StringField("Recipient name", validators=[DataRequired(), Length(max=120)], filters=[strip])
    phone = StringField("Mobile number", validators=[DataRequired(), Length(max=40)], filters=[strip])
    line1 = StringField("Street address", validators=[DataRequired(), Length(max=200)], filters=[strip])
    line2 = StringField("Apartment, unit, building (optional)", validators=[Optional(), Length(max=200)], filters=[strip])
    city = StringField("City", validators=[DataRequired(), Length(max=100)], filters=[strip])
    region = StringField("Province / Region", validators=[DataRequired(), Length(max=100)], filters=[strip])
    postal_code = StringField("Postal code", validators=[DataRequired(), Length(max=20), Regexp(r"^[A-Za-z0-9 -]+$", message="Enter a valid postal code.")], filters=[strip])
    country = StringField("Country", default="Philippines", validators=[DataRequired(), Length(max=60)], filters=[strip])
    is_default = BooleanField("Make this my default address")


class CheckoutAddressForm(AddressForm):
    """Inline "deliver somewhere new" fields on the checkout page (shares the page's CSRF token)."""
    class Meta:
        csrf = False

    save_address = BooleanField("Save this address to my account", default=True)


class CheckoutForm(FlaskForm):
    checkout_token = HiddenField(validators=[DataRequired(), Length(max=64)])
    notes = TextAreaField("Delivery notes (optional)", validators=[Optional(), Length(max=500)])


class DiscountApplyForm(FlaskForm):
    code = StringField("Discount code", validators=[DataRequired(), Length(max=40)], filters=[strip])


class ReviewForm(FlaskForm):
    rating = RadioField("Rating", choices=[(str(i), str(i)) for i in range(5, 0, -1)], validators=[InputRequired("Choose a rating.")])
    title = StringField("Headline", validators=[DataRequired(), Length(min=3, max=120)], filters=[strip])
    body = TextAreaField("Your review", validators=[DataRequired(), Length(min=10, max=2000)], filters=[strip])


class NewsletterForm(FlaskForm):
    email = EmailField("Email", validators=[DataRequired(), Email(), Length(max=255)], filters=[strip])


class CancelOrderForm(FlaskForm):
    reason = StringField("Reason (optional)", validators=[Optional(), Length(max=300)], filters=[strip])


class ProductForm(FlaskForm):
    name = StringField("Product name", validators=[DataRequired(), Length(min=2, max=200)], filters=[strip])
    brand = StringField("Brand / maker", validators=[DataRequired(), Length(max=120)], filters=[strip])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    short_description = StringField("Short description", validators=[DataRequired(), Length(max=300)], filters=[strip])
    description = TextAreaField("Description", validators=[DataRequired(), Length(max=8000)], filters=[strip])
    price = MoneyField("Price (₱)", validators=[DataRequired()])
    compare_at = MoneyField("Compare-at price (₱, optional)", validators=[Optional()])
    stock = IntegerField("Stock", validators=[InputRequired(), NumberRange(min=0, max=100000)])
    size_label = StringField("Size / variant note", validators=[Optional(), Length(max=60)], filters=[strip])
    sizes = StringField("Case sizes shoppers can choose (comma-separated)", validators=[Optional(), Length(max=120)], filters=[strip])
    colors = StringField("Colours shoppers can choose (comma-separated)", validators=[Optional(), Length(max=200)], filters=[strip])
    engraving_fee = MoneyField("Engraving fee (₱). Leave empty if this watch can't be engraved", validators=[Optional()])
    engraving_max = IntegerField("Most engraving characters", default=20, validators=[Optional(), NumberRange(min=1, max=40)])
    origin = StringField("Origin", validators=[Optional(), Length(max=120)], filters=[strip])
    ingredients = TextAreaField("Materials, care, specs or ingredients", validators=[Optional(), Length(max=4000)], filters=[strip])
    status = SelectField("Status", choices=[(s, s.title()) for s in PRODUCT_STATUSES])
    is_featured = BooleanField("Feature on homepage")
    image = FileField("Add image (JPG, PNG, WebP · max 4 MB)")
    make_cover = BooleanField("Use the new photo as the cover image", default=True)
    image_url = StringField("…or image URL (https)", validators=[Optional(), Length(max=500), Regexp(r"^https://", message="Use an https:// URL.")], filters=[strip])

    def validate_sizes(self, field):
        parts = [p.strip() for p in (field.data or "").split(",") if p.strip()]
        if len(set(parts)) != len(parts) or any(len(p) > 12 for p in parts) or len(parts) > 12:
            raise ValidationError("Use up to 12 different sizes, each under 12 characters, e.g. 38 mm, 42 mm.")
        field.data = ",".join(parts)

    def validate_colors(self, field):
        parts = [p.strip() for p in (field.data or "").split(",") if p.strip()]
        if len(set(parts)) != len(parts) or any(len(p) > 24 for p in parts) or len(parts) > 10:
            raise ValidationError("Use up to 10 different colours, each under 24 characters, e.g. Black, Silver, Rose Gold.")
        field.data = ",".join(parts)

    def validate_engraving_fee(self, field):
        if field.minor is not None and field.minor < 0:
            raise ValidationError("The fee can't be negative (use 0 for free engraving).")

    def validate_price(self, field):
        if field.minor is None or field.minor <= 0:
            raise ValidationError("Price must be greater than zero.")

    def validate_compare_at(self, field):
        if field.minor is not None and self.price.minor is not None and field.minor <= self.price.minor:
            raise ValidationError("Compare-at price must be higher than the price.")


class CategoryForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired(), Length(max=80)], filters=[strip])
    description = StringField("Description", validators=[Optional(), Length(max=300)], filters=[strip])
    icon = StringField("Lucide icon name", default="package", validators=[DataRequired(), Length(max=40), Regexp(r"^[a-z0-9-]+$")], filters=[strip])
    position = IntegerField("Sort position", default=0, validators=[InputRequired(), NumberRange(min=0, max=999)])


class DiscountForm(FlaskForm):
    code = StringField("Code", validators=[DataRequired(), Length(min=3, max=40), Regexp(r"^[A-Za-z0-9_-]+$", message="Letters, numbers, - and _ only.")], filters=[strip])
    description = StringField("Description", validators=[Optional(), Length(max=200)], filters=[strip])
    kind = SelectField("Type", choices=[("percent", "Percent off"), ("fixed", "Fixed amount (₱)")])
    value = StringField("Value", validators=[DataRequired()], filters=[strip])
    min_subtotal = MoneyField("Minimum subtotal (₱)", validators=[Optional()])
    max_uses = IntegerField("Max uses (blank = unlimited)", validators=[Optional(), NumberRange(min=1, max=1_000_000)])
    starts_at = DateTimeLocalField("Starts", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    ends_at = DateTimeLocalField("Ends", format="%Y-%m-%dT%H:%M", validators=[Optional()])
    is_active = BooleanField("Active", default=True)

    def validate_value(self, field):
        if self.kind.data == "percent":
            if not field.data.isdigit() or not 1 <= int(field.data) <= 90:
                raise ValidationError("Percent must be a whole number from 1 to 90.")
            self.value_int = int(field.data)
        else:
            try:
                self.value_int = to_minor(field.data)
            except ValueError as exc:
                raise ValidationError(str(exc))
            if self.value_int <= 0:
                raise ValidationError("Amount must be greater than zero.")

    def validate_ends_at(self, field):
        if field.data and self.starts_at.data and field.data <= self.starts_at.data:
            raise ValidationError("End must be after start.")


class OrderStatusForm(FlaskForm):
    status = SelectField("New status", validators=[DataRequired()])
    reason = StringField("Note / cancellation reason", validators=[Optional(), Length(max=300)], filters=[strip])


class StaffReplyForm(FlaskForm):
    reply = TextAreaField("Public reply", validators=[Optional(), Length(max=1000)], filters=[strip])


class OFFSearchForm(FlaskForm):
    class Meta:
        csrf = False  # read-only GET search
    q = StringField("Search Open Food Facts", validators=[DataRequired(), Length(min=2, max=100)], filters=[strip])


class OFFImportForm(FlaskForm):
    barcode = StringField(validators=[DataRequired(), Regexp(r"^\d{6,14}$")], filters=[strip])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    price = MoneyField("Price (₱)", validators=[DataRequired()])
    stock = IntegerField("Stock", default=10, validators=[InputRequired(), NumberRange(min=0, max=100000)])
    publish = BooleanField("Publish immediately")

    def validate_price(self, field):
        if field.minor is None or field.minor <= 0:
            raise ValidationError("Price must be greater than zero.")


class UserAdminForm(FlaskForm):
    role = SelectField("Role", choices=[(r, r.title()) for r in ROLES])
    is_active_account = BooleanField("Account active")


class SettingsForm(FlaskForm):
    shipping_flat = MoneyField("Flat shipping fee (₱)", validators=[DataRequired()])
    free_shipping_threshold = MoneyField("Free shipping over (₱)", validators=[DataRequired()])
    low_stock_threshold = IntegerField("Low-stock alert at", validators=[InputRequired(), NumberRange(min=0, max=1000)])
    store_announcement = StringField("Announcement bar", validators=[Optional(), Length(max=200)], filters=[strip])
    support_email = EmailField("Support email", validators=[DataRequired(), Email(), Length(max=200)], filters=[strip])
    store_name = StringField("Store name (map ad)", validators=[DataRequired(), Length(max=120)], filters=[strip])
    store_address = StringField("Store address (map ad)", validators=[DataRequired(), Length(max=300)], filters=[strip])
    store_hours = StringField("Opening hours", validators=[DataRequired(), Length(max=200)], filters=[strip])
    store_lat = StringField("Map latitude", validators=[DataRequired()], filters=[strip])
    store_lng = StringField("Map longitude", validators=[DataRequired()], filters=[strip])

    def validate_store_lat(self, field):
        try:
            ok = -90 <= float(field.data) <= 90
        except ValueError:
            ok = False
        if not ok:
            raise ValidationError("Latitude is a number from -90 to 90, e.g. 14.5507.")

    def validate_store_lng(self, field):
        try:
            ok = -180 <= float(field.data) <= 180
        except ValueError:
            ok = False
        if not ok:
            raise ValidationError("Longitude is a number from -180 to 180, e.g. 121.0505.")
