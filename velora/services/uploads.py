"""Secure image uploads: extension + real content validation, re-encoding, random filenames."""
import secrets
from pathlib import Path

from flask import current_app
from PIL import Image, UnidentifiedImageError

MAX_DIMENSION = 2400
FORMATS = {"JPEG", "PNG", "WEBP"}


class UploadError(ValueError):
    pass


def save_product_image(file_storage):
    """Validate and store an uploaded image; returns the stored filename."""
    if not file_storage or not file_storage.filename:
        raise UploadError("Choose an image to upload.")
    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
        raise UploadError("Only JPG, PNG or WebP images are allowed.")
    data = file_storage.stream.read(current_app.config["MAX_CONTENT_LENGTH"] + 1)
    if len(data) > current_app.config["MAX_CONTENT_LENGTH"]:
        raise UploadError("Image is too large.")
    if not data:
        raise UploadError("The uploaded file is empty.")
    import io
    try:
        with Image.open(io.BytesIO(data)) as probe:
            probe.verify()  # structural check
        img = Image.open(io.BytesIO(data))
        if img.format not in FORMATS:
            raise UploadError("Unsupported image format.")
        if img.width * img.height > 40_000_000:
            raise UploadError("Image dimensions are too large.")
        img.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise UploadError("That file isn't a valid image.")
    # Re-encode: strips metadata and any non-image payload
    img = img.convert("RGB")
    img.thumbnail((MAX_DIMENSION, MAX_DIMENSION))
    folder = Path(current_app.config["UPLOAD_FOLDER"])
    folder.mkdir(parents=True, exist_ok=True)
    name = f"{secrets.token_hex(12)}.webp"
    img.save(folder / name, "WEBP", quality=86, method=4)
    return name


def delete_upload(filename):
    if not filename or "/" in filename or "\\" in filename or filename.startswith("."):
        return
    path = Path(current_app.config["UPLOAD_FOLDER"]) / filename
    if path.is_file():
        path.unlink()
