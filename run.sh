#!/usr/bin/env sh
# One-click start for CivicPulse on Linux/macOS. Needs Python 3.12+.
set -e
cd "$(dirname "$0")"
[ -x .venv/bin/python ] || python3 -m venv .venv
if [ ! -f .venv/installed.flag ]; then
  echo "Installing packages, first run only..."
  .venv/bin/python -m pip install --disable-pip-version-check -q -r requirements.txt
  touch .venv/installed.flag
fi
NEWDB=0; [ -f db.sqlite3 ] || NEWDB=1
.venv/bin/python manage.py migrate --noinput
[ "$NEWDB" = 1 ] && .venv/bin/python manage.py seed_demo
echo "CivicPulse is running at http://localhost:8001/login/  (Ctrl+C to stop)"
.venv/bin/python manage.py runserver 8001
