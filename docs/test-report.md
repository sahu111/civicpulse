# CivicPulse: Test report

These are actual results from runs on 13 Nov 2026 (Windows 10, Python 3.13.7, Django 5.2.19, SQLite development database, Chromium via Playwright). Raw output is in [coverage-report.txt](coverage-report.txt) and [e2e-report.txt](e2e-report.txt).

## Summary
| Run | Command | Result |
|---|---|---|
| Unit and integration, with coverage | `pytest --cov=. --cov-report=term` | **48 passed**, 0 failed (154.7 s) |
| End-to-end browser | `pytest -m e2e` | **1 passed**, 0 failed (18.0 s) |
| Line coverage (app code, excluding migrations and tests) | | **88%** (1336 statements, 156 missed) |
| Deploy check | `python manage.py check --deploy --settings=config.settings.prod` | No issues (0 silenced) |
| Pending migrations | `python manage.py makemigrations --check --dry-run` | No changes detected |

## Test cases
| Area | Test | What it checks | Result |
|---|---|---|---|
| Authentication | test_register_always_creates_citizen | Sign-up creates a CITIZEN even if `role=ADMIN` is posted; password is hashed | Pass |
| | test_wrong_password_fails_and_logout_ends_session | Wrong password refused; logout clears the session | Pass |
| | test_login_rate_limit_per_email | Login blocked with 429 after repeated attempts | Pass |
| | test_register_rate_limit | 6th sign-up from one IP within the hour gets 429 | Pass |
| Permissions | test_citizen_cannot_open_another_citizens_report | Another citizen gets 404; the owner gets 200 | Pass |
| | test_staff_sees_only_assigned_issues | Unassigned staff 404; assigned staff 200 | Pass |
| | test_citizen_cannot_use_admin_or_staff_urls | Admin action gets 403, `/tasks/` gets 403, nothing changed | Pass |
| | test_anonymous_redirected_to_login | Anonymous user is sent to login | Pass |
| | test_staff_cannot_submit_issue | Staff get 403 on the report form | Pass |
| | test_dashboard_admin_only | Citizen and staff get 403 on dashboard, chart API and export | Pass |
| | test_other_staff_cannot_add_progress | Non-assigned staff get 404 | Pass |
| Issue creation | test_tracking_codes_are_unique_and_formatted | Codes unique and match `CP-YYMM-NNNN` | Pass |
| | test_submit_with_photo_and_reject_fake_image | Valid PNG saved under a random name; an EXE renamed to `.jpg` rejected | Pass |
| | test_missing_coordinates_and_long_title_rejected | Title over 100 characters and missing latitude both rejected | Pass |
| | test_double_submit_creates_one_report | Same report posted twice creates one issue | Pass |
| Status transitions | test_invalid_transition_refused_and_nothing_written | REPORTED to RESOLVED refused; no history row written | Pass |
| | test_reject_requires_reason | Blank reason refused; with a reason, rejected | Pass |
| | test_full_workflow_writes_history_and_notifications | Every step logged; submit needs evidence; notifications sent | Pass |
| | test_reporter_can_reopen_resolved_issue | Only the reporter can reopen; resolved date cleared | Pass |
| | test_events_are_append_only | History rows cannot be saved again or deleted | Pass |
| Assignment | test_reassign_closes_old_assignment | Old assignment gets an end date; new staff notified | Pass |
| Votes | test_vote_only_once | Second vote blocked by the service and the view | Pass |
| | test_staff_cannot_vote | Staff vote refused | Pass |
| Workflow | test_full_flow_through_http | Citizen to admin to staff to admin to citizen, through real endpoints | Pass |
| | test_send_back_clears_pending | Admin send-back keeps work in progress and notifies staff | Pass |
| | test_request_info_notifies_reporter | Request info notifies the reporter | Pass |
| | test_merge_moves_votes_without_duplicates | Duplicate rejected; supporters moved with no double votes | Pass |
| Uploads | test_fake_and_oversized_evidence_rejected | Fake image and a file over 5 MB rejected with a clear message | Pass |
| | test_media_not_public | Photo served only to permitted users; no public `/media/` URL | Pass |
| Map | test_map_shows_only_permitted_issues | Admin all, staff assigned only, citizen the community list (links only to own) | Pass |
| | test_map_requires_login | Anonymous request redirected | Pass |
| Duplicates and smart rules | test_duplicates_near_and_similar_only | Near and similar found; far, different and closed ignored | Pass |
| | test_category_suggestion_title_weighs_double | Keyword category; title counts double | Pass |
| | test_priority_recommendation_explains_itself | HIGH for "live wire near school" with reasons; LOW for "minor graffiti" | Pass |
| | test_jaccard_and_haversine | Similarity and distance formulas | Pass |
| | test_hotspots_threshold | Only cells at or above the minimum count | Pass |
| | test_new_issue_stores_recommendations | Suggestions stored on new reports | Pass |
| | test_admin_detail_shows_rule_based_wording | Panel says "rule-based"; never "machine learning" or "AI model" | Pass |
| | test_suggest_fragment_for_citizens | Form suggestions show category and nearby similar reports | Pass |
| | test_admin_can_correct_category | Admin correction is logged | Pass |
| Analytics | test_summary_metrics_from_known_data | Total, open, resolved, high, overdue, average resolution (10.0 h), by status, weekly trend | Pass |
| | test_dashboard_number_follows_database | Adding a record changes the dashboard total and the chart data | Pass |
| CSV export | test_csv_export_filters_and_neutralises_formulas | Filter applied; `=` and `+` cells prefixed with `'` | Pass |
| Staff management | test_staff_management | Create staff; can't deactivate staff with open tasks; can't change own role; citizen 403 | Pass |
| Security | test_security_headers | CSP, X-Frame-Options DENY, nosniff, Referrer-Policy | Pass |
| | test_csrf_enforced_on_post | POST without a CSRF token gets 403; nothing saved | Pass |
| | test_prod_settings_are_hardened | DEBUG off, secure cookies, SSL redirect | Pass |
| Seed data | test_seed_demo_creates_every_role_and_status | All roles and statuses created; safe to run twice | Pass |
| End to end | test_full_workflow_in_browser | Chromium: citizen reports, admin reviews and assigns, staff starts, uploads evidence and submits, admin verifies, citizen confirms | Pass |

## Manual checks (browser)
| Check | Result |
|---|---|
| Landing page, sidebar collapse at 375 px, no sideways scroll | Pass |
| No external requests except OpenStreetMap tiles; no console errors | Pass |
| Map: 8 demo pins in status colours, filters, popups | Pass |
| Admin overview: 3 charts render; no CSP violations | Pass |

## Notes
- The browser test runs in its own pytest process (`pytest -m e2e`). Inside the long coverage run it hung on this Windows machine, while it passed every time on its own (about 20 s). Running it separately is the documented approach.
- Rate-limit tests allow for the fixed one-minute window rolling over during the test.
