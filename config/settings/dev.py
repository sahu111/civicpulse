from .base import *  # noqa: F401,F403

DEBUG = True
# Lets a fresh clone run with no .env file. Local development only: prod.py refuses an empty key.
SECRET_KEY = SECRET_KEY or "django-insecure-local-dev-only-not-for-production"  # noqa: F405
DEMO_PASSWORD = DEMO_PASSWORD or "demo1234"  # noqa: F405
