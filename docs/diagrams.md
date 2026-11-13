# CivicPulse: Diagrams

All diagrams are Mermaid. They render on GitHub, in VS Code (Markdown Preview Mermaid) and at mermaid.live.

## Use cases

```mermaid
flowchart LR
  C([Citizen]) --- R[Report issue]
  C --- T[Track own reports]
  C --- V[Support community report]
  C --- CF[Confirm or reopen]
  S([Staff]) --- K[View assigned tasks]
  S --- W[Start work and add notes]
  S --- E[Upload evidence and submit]
  A([Admin]) --- RV[Review, prioritise, reject]
  A --- AS[Assign or reassign]
  A --- M[Merge duplicates]
  A --- VR[Verify or send back]
  A --- AN[Analytics and CSV export]
  A --- SM[Manage staff]
```

## Status workflow (state diagram)

```mermaid
stateDiagram-v2
  [*] --> REPORTED: citizen submits
  REPORTED --> UNDER_REVIEW: admin
  REPORTED --> REJECTED: admin + reason
  UNDER_REVIEW --> REJECTED: admin + reason
  UNDER_REVIEW --> ASSIGNED: admin picks staff
  ASSIGNED --> IN_PROGRESS: assigned staff
  IN_PROGRESS --> RESOLVED: admin, after staff submitted evidence
  RESOLVED --> UNDER_REVIEW: reporter says not fixed
  RESOLVED --> [*]: reporter confirms
  REJECTED --> [*]
```

## Activity: from report to resolution

```mermaid
flowchart TD
  A[Citizen fills form and drops pin] --> B{Valid input and photo?}
  B -- no --> A
  B -- yes --> C[Create issue, tracking code, history entry; notify admins]
  C --> D[Admin reviews and sees recommendations]
  D --> E{Duplicate or invalid?}
  E -- duplicate --> F[Merge into existing report]
  E -- invalid --> G[Reject with reason]
  E -- valid --> H[Assign staff]
  H --> I[Staff starts work and adds notes]
  I --> J[Staff uploads evidence and submits]
  J --> K{Admin verifies}
  K -- not done --> I
  K -- done --> L[Resolved; citizen notified]
  L --> M{Citizen confirms?}
  M -- yes --> N[Closed]
  M -- no --> D
```

## Sequence: a status change

```mermaid
sequenceDiagram
  actor Admin
  participant View as IssueActionView
  participant Perm as permissions.py
  participant Svc as services.change_status
  participant DB as Database
  Admin->>View: POST /issues/CODE/action/ (action=review)
  View->>Perm: can_view_issue(user, issue)
  Perm-->>View: allowed
  View->>Svc: change_status(issue, UNDER_REVIEW, admin)
  Svc->>DB: BEGIN; SELECT ... FOR UPDATE
  Svc->>Svc: check transition table and role rule
  Svc->>DB: UPDATE issue; INSERT IssueEvent; INSERT Notification(s)
  Svc->>DB: COMMIT
  View-->>Admin: redirect to detail with a toast
```

## Entity relationships

```mermaid
erDiagram
  USER ||--o{ ISSUE : reports
  USER ||--o{ ISSUE : "assigned to"
  ISSUE ||--o{ ISSUE_EVENT : history
  USER ||--o{ ISSUE_EVENT : performs
  ISSUE ||--o{ ISSUE_MEDIA : has
  ISSUE ||--o{ ISSUE_ASSIGNMENT : has
  USER ||--o{ ISSUE_ASSIGNMENT : "works on"
  ISSUE ||--o{ ISSUE_VOTE : supported
  USER ||--o{ ISSUE_VOTE : casts
  USER ||--o{ NOTIFICATION : receives
  ISSUE ||--o{ NOTIFICATION : about
  ISSUE |o--o{ ISSUE : "merged into"
  USER { int id string email UK string role }
  ISSUE { string tracking_code UK string status string priority string category decimal latitude decimal longitude datetime created_at datetime resolved_at }
  ISSUE_EVENT { string kind string old_status string new_status text note }
  ISSUE_VOTE { int issue_id int user_id "unique together" }
```

## Architecture

```mermaid
flowchart LR
  B[Browser: HTML, Tailwind, HTMX, Alpine, Leaflet, Chart.js] -->|HTTPS| D[Django views]
  B -->|tiles| OSM[(OpenStreetMap tiles)]
  D --> P[accounts/permissions.py]
  D --> SV[issues/services.py]
  D --> SM[issues/smart.py]
  D --> Q[analytics/queries.py]
  SV --> N[notifications/services.py]
  SV --> ORM[Django ORM]
  Q --> ORM
  ORM --> DB[(PostgreSQL or SQLite)]
  SV --> FS[(media/ uploads)]
```
