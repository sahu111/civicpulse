# Limitations and future work

## Known limitations
- **Rule-based recommendations only.** Category, priority and duplicate suggestions use keyword lists, scores and distance (`issues/smart_config.py`). They can miss synonyms and other languages. An admin always decides.
- **Rate-limit storage.** django-ratelimit uses Django's default in-process cache. With several gunicorn workers each one counts separately, so production should use a shared cache such as Redis or Memcached.
- **Content Security Policy** allows `'unsafe-inline'` (small inline page scripts) and `'unsafe-eval'` (needed by the standard Alpine.js build). Moving scripts to files and switching to Alpine's CSP build would allow a stricter policy.
- **Map tiles need internet** and follow the OpenStreetMap tile usage policy (light use, attribution shown). Offline, the app shows a notice and pins still work.
- **No email or SMS.** Notifications are in-app only.
- **Local file storage.** Uploads live in `media/` and are served through a permission check. A hosted deployment needs persistent storage.
- **Database during development.** The local setup used SQLite (`DB_ENGINE=sqlite`) because the PostgreSQL user hadn't been created yet. The code targets PostgreSQL (psycopg 3) and runs unchanged on it once `DB_ENGINE=postgres` is set.
- **Tracking-number locking.** SQLite ignores `SELECT ... FOR UPDATE`, but it serialises writes. On PostgreSQL the counter row is truly locked.
- **Single city.** There is no tenancy or ward boundaries; hotspots are a simple coordinate grid.

## Future enhancements
- Email or push notifications, and SMS for citizens without smartphones.
- Ward or zone boundaries (GeoJSON) and automatic routing to departments.
- Service-level reports per department, and public transparency pages.
- Multilingual interface and keyword lists.
- Offline-first progressive web app for field staff.
- A trained text classifier, evaluated against the current rules, once enough labelled reports exist.
