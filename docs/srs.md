# CivicPulse: Software Requirements Specification

## 1. Abstract
CivicPulse is a web application where citizens report civic problems (roads, street lights, water, drainage, sanitation, electricity, parks) with a description, photo and map location. The city reviews each report, sets its priority and assigns it to field staff. Staff record progress and upload completion evidence. Admins verify the work and citizens confirm the fix. Every step is logged and notified. Rule-based recommendations help admins categorise, prioritise and spot duplicates. An analytics dashboard summarises performance.

## 2. Problem statement
Civic complaints are often lost across phone calls and paper registers. Citizens can't see progress, duplicates waste effort, and officials have no reliable data on workload, delays or problem areas.

## 3. Objectives
- One place to report issues with exact location and photo evidence.
- A transparent, enforced workflow: Reported, Under review, Assigned, In progress, Resolved, plus Rejected (with a reason).
- Role-based access for Citizen, Staff and Admin, enforced on the server.
- A complete, unchangeable history of every action.
- Rule-based help: category and priority recommendations, duplicate detection, hotspots and overdue alerts.
- Live analytics and CSV export for administrators.

## 4. Scope
**In scope:** web app (desktop, tablet and phone), local file storage, in-app notifications, OpenStreetMap maps, a single city.
**Out of scope:** email or SMS delivery, native mobile apps, payments, multi-city tenancy, machine-learning models.

## 5. Users and roles
| Role | Main goals |
|---|---|
| Citizen | Report issues, track own reports, support community reports, confirm or reopen resolved reports |
| Staff | See assigned tasks, start work, add progress notes, upload evidence, submit for verification |
| Admin | Review, prioritise, assign or reassign, request info, reject, merge duplicates, verify or send back, manage staff, analytics, export |

## 6. Functional requirements
| ID | Requirement |
|---|---|
| FR-1 | Public registration always creates a Citizen. Login by email and password, logout, profile and password change. |
| FR-2 | Citizens submit an issue: title (5-100 characters), description (10-1000), category, location text, latitude and longitude (picked on a map), optional photo and notes. |
| FR-3 | Each issue gets a unique tracking code `CP-YYMM-NNNN`, generated inside a transaction. |
| FR-4 | Status changes follow the transition table only (see diagrams). Rejecting requires a reason. Resolving requires a staff submission with at least one evidence photo. |
| FR-5 | Every action writes an IssueEvent (append-only) and notifies the people concerned. |
| FR-6 | Reassignment closes the previous assignment record and opens a new one. |
| FR-7 | Citizens can support a community report once (unique constraint). |
| FR-8 | Merging closes the duplicate as Rejected and moves its supporters without double-counting. |
| FR-9 | The map shows only the issues the signed-in role may see, with status colours, filters, popups and a tile-failure notice. |
| FR-10 | Rule-based recommendations for category, priority (with reasons) and duplicates, shown on the report form and the admin issue page, labelled as recommendations, and correctable by the admin. |
| FR-11 | The admin dashboard shows totals, open, high-priority open, resolved, average resolution time, overdue, weekly trend, by status, by category, hotspots and staff workload, all from database queries. |
| FR-12 | Admin-only CSV export of filtered reports, with spreadsheet formula injection neutralised. |
| FR-13 | Admins create staff accounts, change roles, and activate or deactivate accounts (not their own; not staff with open tasks). |

## 7. Non-functional requirements
- **Security:** CSRF on every POST, hashed passwords, secure cookies and HSTS in production, CSP and other security headers, rate limits on login, register, report and export, validated uploads served only through a permission check, no SSRF-prone URL fetching.
- **Usability:** responsive at 375 px and up, keyboard-reachable controls, clear empty, loading and error states.
- **Cost:** free and open-source tools only; no paid APIs.
- **Maintainability:** thin views, business rules in `services.py`, access rules in `accounts/permissions.py`, tunable values in `smart_config.py`.
- **Testability:** automated unit, integration and browser end-to-end tests.

## 8. Data model
Seven core models: User, Issue, IssueEvent, IssueMedia, IssueAssignment, IssueVote and Notification, plus a TrackingCounter helper. See the ER diagram in [diagrams.md](diagrams.md).
