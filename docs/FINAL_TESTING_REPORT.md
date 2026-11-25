# Final testing report

## Local verification performed

The following evidence was observed in this workspace:

- Python source compilation
- Automated pytest suite
- Flask migration generation and upgrade
- `/health` database response
- Security header response
- Public event, calendar, leaderboard, and certificate verification routes

The current suite contains authentication, route authorization, registration, capacity, attendance, certificate, feedback, resource conflict, budget, hours, and rule-based recommendation tests.

## Automated test command

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

## Target-environment acceptance still required

Before handover, the college team must execute acceptance tests against an HTTPS MySQL deployment:

1. Admin creates and manages accounts, departments, clubs, resources, and approvals.
2. Coordinator creates events and manages registrations, volunteers, tasks, attendance, budgets, galleries, and reports.
3. Student registers, applies, updates tasks, receives notifications, obtains attendance, submits feedback, downloads certificates, and views recommendations.
4. Public certificate verification accepts valid IDs and rejects invalid or revoked IDs.
5. Desktop, laptop, tablet, and mobile layouts are accepted.
6. Backup and restore are tested against a separate database.
7. TLS, session, CSRF, file upload, and authorization controls are verified.
