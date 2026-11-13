# CivicPulse

A smart city issue reporting and management web app, built with Django as an individual MCA/MSc IT final-year project.

Citizens report problems (potholes, broken lights, leaks) with a photo and a map pin. Admins review, prioritise and assign field staff. Staff record progress and upload completion evidence. Admins verify, and the citizen confirms the fix. Every step is stored in an append-only history.

"Smart" features (category and priority recommendations, duplicate detection, hotspots, overdue detection) are **simple keyword, score and distance rules**. They are not machine learning. All their settings are in `issues/smart_config.py`.

## Stack

Python 3.12+, Django 5.2, PostgreSQL (SQLite fallback for local development), Tailwind CSS v4, HTMX, Alpine.js, Leaflet with OpenStreetMap tiles, Chart.js, django-ratelimit, Pillow, pytest, pytest-django and Playwright. Everything is free and open source. All JS and CSS is served from `static/vendor/`, so the app runs offline apart from map tiles.

## Install

```bash
git clone <your-repo-url> civicpulse && cd civicpulse
python -m venv .venv
.venv\Scripts\activate          # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
npm install                      # only needed to rebuild Tailwind CSS
```

## Configure

Copy `.env.example` to `.env`, then set at least `SECRET_KEY`:

```bash
python -c "from django.core.management.utils import get_random_secret_key as g; print(g())"
```

**Database**
- **PostgreSQL (target):** create the database and user once, as the `postgres` superuser:
  ```sql
  CREATE USER civicpulse_user WITH PASSWORD 'choose-a-local-password' CREATEDB;
  CREATE DATABASE civicpulse OWNER civicpulse_user;
  ```
  Then set `DB_ENGINE=postgres` and the `DB_*` values in `.env`. (`CREATEDB` lets pytest create its test database.)
- **SQLite (quick local fallback):** set `DB_ENGINE=sqlite`. No other settings are needed.

## Migrate, seed and run

```bash
python manage.py migrate
python manage.py seed_demo        # demo users for every role + 8 issues in every status
npm run build:css                 # after changing Tailwind classes in templates
python manage.py runserver
```

`seed_demo` prints the demo accounts and a generated password once. To choose the password yourself, set `DEMO_PASSWORD` in `.env`. Demo coordinates are fictional points.

| Role | Email |
|---|---|
| Admin | admin@civicpulse.test |
| Staff | staff1@civicpulse.test, staff2@civicpulse.test |
| Citizen | citizen1@civicpulse.test, citizen2@civicpulse.test |

The optional Django admin site is at `/django-admin/` (`python manage.py createsuperuser`).

## Test

```bash
pytest --cov=. --cov-report=term-missing            # unit + integration tests with coverage
playwright install chromium                         # once, for the browser test
pytest -m e2e                                       # end-to-end browser test (runs on its own)
python manage.py check --deploy --settings=config.settings.prod
```

Actual results are recorded in [docs/test-report.md](docs/test-report.md).

## Project layout

| Path | Contents |
|---|---|
| `config/settings/` | `base.py`, `dev.py`, `prod.py` (all read from `.env`) |
| `accounts/` | custom User with role, auth views, staff management, `permissions.py` (all access rules) |
| `issues/` | models, `services.py` (workflow rules), `smart.py` and `smart_config.py`, CSV export, map |
| `analytics/` | `queries.py` (every dashboard number), dashboard and chart JSON |
| `notifications/` | in-app notifications |
| `core/` | landing page, error pages, layout helpers, security headers, `seed_demo` |
| `templates/`, `static/` | server-rendered pages, built CSS, vendored JS |
| `tests/` | unit, integration and e2e tests |
| `docs/` | SRS, diagrams, API, test report, user manual, limitations, screenshots |

## Deployment (optional)

Use `config.settings.prod` with gunicorn and whitenoise: `DEBUG=False`, real `ALLOWED_HOSTS`, HTTPS, and persistent storage for `media/`. Run `python manage.py collectstatic` first. Local development is the primary demo. See [docs/limitations.md](docs/limitations.md).

## Known limitations

See [docs/limitations.md](docs/limitations.md). The main ones:
- Rate limits use the in-process cache, so counts aren't shared across multiple workers.
- Map tiles need internet.
- The CSP allows inline scripts and `unsafe-eval`, which Alpine.js needs.
- There is no email delivery; notifications are in-app only.
