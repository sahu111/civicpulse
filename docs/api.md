# CivicPulse: JSON and HTTP endpoints

The app is server-rendered. Three JSON endpoints feed the map and charts, and one returns an HTMX fragment. All of them need a signed-in session and are scoped by role on the server. Django REST Framework and drf-spectacular are installed but not used, because these few endpoints didn't need them.

## GET /api/map/
Map pins visible to the signed-in user: admin sees all, staff only assigned issues, citizens the community list (no rejected or merged reports).

| Query param | Values |
|---|---|
| `status` | `REPORTED`, `UNDER_REVIEW`, `ASSIGNED`, `IN_PROGRESS`, `RESOLVED`, `REJECTED` |
| `category` | `ROADS`, `STREETLIGHT`, `WATER`, `DRAINAGE`, `SANITATION`, `ELECTRICITY`, `PARKS`, `OTHER` |

```json
{"issues": [{"code": "CP-2611-0001", "title": "Deep pothole outside primary school",
  "lat": 21.1458, "lng": 79.0882, "status": "REPORTED", "status_label": "Reported",
  "category": "ROADS", "category_label": "Roads and potholes",
  "url": "/issues/CP-2611-0001/"}]}
```
`url` is `null` when the user can't open that issue. Responses are limited to 1000 issues. Anonymous requests get 302 to `/login/`.

## GET /api/analytics/charts/ (admin only)
```json
{"by_status":   [{"key": "REPORTED", "label": "Reported", "count": 2}],
 "by_category": [{"key": "ROADS", "label": "Roads and potholes", "count": 1}],
 "weekly": {"labels": ["21 Sep"], "reported": [0], "resolved": [0]}}
```
Other roles get 403.

## GET /issues/suggest/ (citizen only, HTMX fragment)
Params: `title`, `description`, `category`, `latitude`, `longitude`. Returns an HTML snippet with the category recommendation and similar open reports within the duplicate radius.

## GET /admin-panel/export/ (admin only)
Returns a CSV of reports with the same `q`, `status`, `category`, `priority` and `sort` filters as `/issues/`. Columns: tracking code, title, category, priority, status, created, resolved. Cells starting with `= + - @`, tab or carriage return get a `'` prefix. Rate limited (default 10 per minute).

## POST /issues/<code>/action/
A form endpoint (CSRF required) used by all workflow buttons. The field `action` is one of:
`review, reject, assign, priority, category, start, progress, evidence, submit, resolve, send_back, confirm, reopen, request_info, merge, comment`.
Extra fields: `note`, `staff` (id), `priority`, `category`, `target` (tracking code), `photo` (file).
Every action is permission-checked in `issues/services.py`: 403 when the role isn't allowed, 404 when the user can't see the issue.

## GET /issues/<code>/media/<id>/
Streams an uploaded photo after the same visibility check as the issue page. There is no public media URL.

## Rate limits (429 when exceeded)
| Endpoint | Key | Default (env var) |
|---|---|---|
| POST /login/ | IP | 10/m (`RATE_LOGIN_IP`) |
| POST /login/ | email | 5/m (`RATE_LOGIN_EMAIL`) |
| POST /register/ | IP | 5/h (`RATE_REGISTER`) |
| POST /issues/new/ | user | 10/h (`RATE_REPORT`) |
| GET /admin-panel/export/ | user | 10/m (`RATE_EXPORT`) |
