from django.core.exceptions import ValidationError
from PIL import Image

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
ALLOWED_FORMATS = {"JPEG": "image/jpeg", "PNG": "image/png", "WEBP": "image/webp"}


def validate_image(upload):
    """Check size and real content (not the file name). Returns the verified MIME type."""
    if upload.size > MAX_UPLOAD_BYTES:
        raise ValidationError("Images must be 5 MB or smaller.")
    try:
        upload.seek(0)
        with Image.open(upload) as img:
            fmt = img.format
            img.verify()
    except Exception:
        raise ValidationError("Upload a valid JPEG, PNG or WebP image.")
    finally:
        upload.seek(0)
    if fmt not in ALLOWED_FORMATS:
        raise ValidationError("Only JPEG, PNG and WebP images are allowed.")
    return ALLOWED_FORMATS[fmt]
