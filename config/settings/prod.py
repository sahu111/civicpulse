from .base import *  # noqa: F401,F403

from django.core.exceptions import ImproperlyConfigured

DEBUG = False
DEMO_PASSWORD = ""
if not SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("Set SECRET_KEY in .env for production.")
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
