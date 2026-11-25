# Project Audit Report

## 1. Executive Summary
This audit covers the **College Event and Volunteer Management System** (Flask, Flask-SQLAlchemy, Flask-Login, Flask-WTF, Flask-Migrate, Bootstrap 5, Chart.js, MySQL target). All application structure, authentication, role-based access control (RBAC), database models, migrations, automated tests, and smoke tests were reviewed against the actual codebase.

- **Production Database Target:** MySQL (`mysql+pymysql://...` via `ProductionConfig` and `docker-compose.yml`) remains unchanged.
- **Verification Environment:** Preliminary verification was executed using SQLite (persistent `sqlite:///college_events.db` for Flask-Migrate CLI checks and ephemeral `sqlite:///:memory:` for `pytest` and `scripts/smoke_test_sqlite.py`) because Docker and a MySQL server/client are unavailable in this environment.
- **MySQL Status:** **NOT TESTED** against a live MySQL server.

## 2. Architecture & Project Structure
- **Application Factory:** `app/__init__.py` (`create_app`) registers 15 blueprints (`main`, `auth`, `admin`, `coordinator`, `student`, `events`, `attendance`, `tasks`, `notifications`, `certificates`, `analytics`, `feedback`, `community`, `advanced`, `assistance`), configures SQLAlchemy, Flask-Migrate, CSRFProtect, Flask-Login, security headers, error handlers (`403`, `404`, `413`, `500`), `/health`, and CLI commands (`init-db`, `create-admin`, `seed-demo`).
- **Database Models (`app/models.py`):** 21 SQLAlchemy models (`Role`, `Department`, `Club`, `EventCategory`, `Event`, `EventRegistration`, `VolunteerApplication`, `VolunteerAssignment`, `VolunteerTask`, `Attendance`, `Notification`, `Certificate`, `Feedback`, `EventGallery`, `VolunteerHours`, `EventBudget`, `EventExpense`, `Resource`, `ResourceBooking`, `StudentInterest`, `User`) with foreign keys, unique constraints, and check constraints.
- **Templates & Dashboards:** Role-specific templates exist at `app/templates/dashboards/admin.html`, `coordinator.html`, and `student.html`, extending `base_dashboard.html`.

## 3. Authentication & RBAC Audit Findings
- **Single Shared Login (`app/auth/routes.py`):**
  - `/auth/login` uses `LoginForm` and `User.check_password()` (Werkzeug password hashing).
  - If `current_user.is_authenticated` is already `True`, `/auth/login` redirects to `dashboard_endpoint(current_user.role_name)` without unconditionally calling `logout_user()`.
  - Invalid credentials (unknown email or wrong password) do not call `login_user()`, flash `"Invalid email or password."`, and return HTTP `200` on `auth/login.html`.
  - `/auth/logout` is `@login_required`, calls `logout_user()`, and redirects to `main.index`.
- **Role-Based Access Control (`app/decorators.py`):**
  - `roles_required(*roles)` redirects unauthenticated requests via `login_required` (HTTP `302` to `/auth/login?next=...`) and calls `abort(403)` when `current_user.role_name not in roles`.
  - `@roles_required("admin")`, `@roles_required("coordinator")`, and `@roles_required("student")` are enforced on `admin.dashboard`, `coordinator.dashboard`, and `student.dashboard` respectively.
- **Root Cause of Earlier Smoke-Test Failures:**
  - The earlier `scripts/smoke_test_sqlite.py` did not call `/auth/logout` between role logins in the shared Flask `test_client()` cookie jar. Because `app/auth/routes.py` preserves an already authenticated session when visiting `/auth/login`, subsequent login attempts remained authenticated as `admin`.
  - `scripts/smoke_test_sqlite.py` was corrected to log out between independent scenarios, add explicit unauthenticated checks, fix `EXPECTED_HEADINGS`, and compute totals from `len(results)`.

## 4. Database & Migration Verification
| Check | Command | Database URI | Persistence | Outcome |
|---|---|---|---|---|
| Default app URI inspection | `python -c "import os; from app import create_app; print(create_app().config['SQLALCHEMY_DATABASE_URI'])"` | `sqlite:///college_events.db` | Persistent file (SQLite `instance/`) | Verified |
| Alembic upgrade | `$env:FLASK_APP = "run.py"; flask db upgrade` | `sqlite:///college_events.db` (`SQLiteImpl`) | Persistent file | Exited `0` |
| Alembic revision | `$env:FLASK_APP='run.py'; flask db current` | `sqlite:///college_events.db` (`SQLiteImpl`) | Persistent file | `3d033d72dd65 (head)` |
| Automated test suite | `pytest -v` | `sqlite:///:memory:` (`TestConfig`) | Ephemeral in-memory | `35 passed` in `16.47s` |
| Smoke test | `$env:PYTHONPATH='.'; python scripts/smoke_test_sqlite.py` | `sqlite:///:memory:` (`DATABASE_URL` override) | Ephemeral in-memory | `24 passed, 0 failed` |
| MySQL migrations & tests | Not executed | `mysql+pymysql://...` | Persistent MySQL | **NOT TESTED** |

**In-Memory SQLite Limitations:**
- Schema and data created during `pytest` and `scripts/smoke_test_sqlite.py` are discarded on process exit and do not verify persistent storage or MySQL-specific behavior (strict SQL modes, case sensitivity, `DECIMAL`/`DATETIME` handling, connection pooling).
