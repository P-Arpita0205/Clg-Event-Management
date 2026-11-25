# Campus Connect — College Event & Volunteer Management System

Campus Connect is a role-based Flask web application for managing college events, compulsory & optional student registrations, volunteer workflows, QR/unique-key attendance check-in, post-event verifiable PDF certificates, campus resource bookings, and analytics.

## Tech Stack

- **Backend:** Python 3.10+, Flask 3.1, Flask-SQLAlchemy, Flask-Migrate (Alembic), Flask-Login, Flask-WTF (CSRF protection)
- **Database:** SQLite (local development) / MySQL 8 via PyMySQL (production)
- **Frontend:** Bootstrap 5, Font Awesome, Chart.js, [`html5-qrcode`](https://github.com/mebjas/html5-qrcode) (live camera & image QR scanning)
- **PDF & QR Generation:** ReportLab, `qrcode`, Pillow
- **Deployment:** Gunicorn, Docker & Docker Compose, Nginx

---

## Key Features

### Students
- Self-registration with administrator approval before login.
- **Compulsory event alerts:** Pending compulsory events appear at the top of the student dashboard with a one-click **Register now** action; compulsory registrations cannot be cancelled.
- **Attendance QR passes & unique keys:** Inline QR codes and verifiable short unique keys (`P-<id>-<hex>` for participants, `V-<id>-<hex>` for approved volunteers) with one-click copy across the dashboard, registrations, volunteering, and event detail pages.
- **Volunteering & tasks:** Apply to volunteer for published events, view assigned roles, update task progress (`assigned`, `in_progress`, `completed`), and track deadlines.
- **Certificates:** Automatically receive **Participation (`CPC-`)** and **Volunteer (`CVC-`)** PDF certificates after an event ends once QR attendance has been scanned.
- Feedback submission (with optional anonymity), event recommendations based on interests/department, and notifications.

### Coordinators
- Create and edit events (including multi-day dates, volunteer limits, poster uploads, and **Registration compulsory** toggle) and submit for admin approval.
- View confirmed participants and **Pending compulsory registrations** (eligible students who have not yet registered).
- Approve/reject volunteer applications, assign volunteer roles, and assign/manage volunteer tasks with deadlines.
- **Live QR code check-in scanner:** Scan student participant and volunteer QR codes via webcam or uploaded QR image, enter a student's unique key (`P-...` / `V-...`) if the scanner is unavailable, or record manual attendance (reporting only).
- Mark events as ended (`POST /events/<id>/complete`) to trigger automatic certificate issuance for QR-verified attendees, review feedback & extracted themes, manage event budgets/expenses, upload event gallery photos, and book campus resources with conflict detection.

### Administrators
- Approve or reject student sign-ups and toggle student account status.
- Approve, reject, edit, end, or delete events; issue coordinator certificates (`CCC-`).
- Manage departments, campus clubs, and campus resources (auditoriums, seminar halls, labs, etc.).
- View department participation, category mix, and event lifecycle charts on the admin dashboard and analytics page.
- Publicly verify any certificate via `/certificates/verify/<certificate_id>`.

---

## Project Structure

```text
college_event_management/
├── app/
│   ├── __init__.py          # App factory, CLI commands (init-db, create-admin, seed-demo), /health
│   ├── models.py            # SQLAlchemy models and attendance_key / event end helpers
│   ├── decorators.py        # Role-based access control decorator
│   ├── admin/               # Admin dashboard, student & event management
│   ├── advanced/            # Galleries, budgets/expenses, resources & bookings, leaderboard
│   ├── analytics/           # Admin analytics views
│   ├── assistance/          # Rule-based event recommendations, role hints, feedback themes
│   ├── attendance/          # QR pass generation, live scan API, validation & reports
│   ├── auth/                # Login, registration, logout
│   ├── certificates/        # PDF certificate generation, QR gating, verification & history
│   ├── community/           # Departments, clubs, monthly calendar
│   ├── coordinator/         # Coordinator dashboard, events & volunteer applications
│   ├── events/              # Event CRUD, registrations, compulsory tracking, volunteers
│   ├── feedback/            # Event feedback submission & review
│   ├── main/                # Landing page & role redirect
│   ├── notifications/       # In-app notification feed & read state
│   ├── student/             # Student dashboard, registrations & volunteering views
│   ├── tasks/               # Volunteer task assignment & status updates
│   ├── static/              # Custom CSS and JavaScript
│   └── templates/           # Jinja2 templates
├── deploy/                  # Nginx reverse-proxy example config
├── docs/                    # Deployment, backup/restore, manuals & security docs
├── migrations/              # Alembic database migrations
├── scripts/                 # MySQL backup/restore scripts & SQLite smoke tests
├── tests/                   # Pytest test suite
├── config.py                # Config & ProductionConfig
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── requirements.txt
├── requirements-dev.txt
└── run.py
```

---

## Environment Variables

Copy `.env.example` to `.env` for local development. In production (`APP_ENV=production`), `create_app()` enforces a non-default `SECRET_KEY` and a `mysql://` or `mysql+pymysql://` `DATABASE_URL`.

| Variable | Description | Example / Default |
|---|---|---|
| `FLASK_APP` | Flask entrypoint | `run.py` |
| `FLASK_ENV` | Flask environment | `development` |
| `APP_ENV` | App environment (`development` or `production`) | `development` |
| `SECRET_KEY` | Strong random secret key (32+ chars in production) | *(generate with `secrets.token_urlsafe(48)`)* |
| `DATABASE_URL` | SQLAlchemy DB URI | `sqlite:///college_events.db` (dev) / `mysql+pymysql://...` (prod) |
| `SESSION_COOKIE_SECURE` | Set `true` behind HTTPS in production | `false` |

---

## Local Development Setup

### Windows (PowerShell)

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Edit `.env` if needed (for local SQLite, set `DATABASE_URL=sqlite:///college_events.db`), then initialize the database:

```powershell
flask db upgrade
flask init-db
flask run
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
flask db upgrade
flask init-db
flask run
```

Open `http://127.0.0.1:5000`.

### Optional Demo Data (Local Only)

```bash
flask seed-demo
```

This seeds idempotent demo accounts (password: `CampusDemo123!`) for `admin@college.edu`, `coordinator@college.edu`, and `student@college.edu`. **Never run `seed-demo` in production.**

For production admin creation, use:

```bash
flask create-admin
```

---

## Running Tests

```bash
pip install -r requirements-dev.txt
pytest -v
```

---

## Production Deployment

### Option 1: Docker Compose (with MySQL 8)

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export MYSQL_PASSWORD="strong-db-password"
export MYSQL_ROOT_PASSWORD="strong-root-password"
export APP_ENV="production"

docker compose up --build -d
docker compose exec web flask db upgrade
docker compose exec web flask init-db
docker compose exec web flask create-admin
```

Verify health at `/health` (returns `{"status": "ok", "database": "connected"}`). Put Nginx with TLS/HTTPS in front using [deploy/nginx.conf.example](deploy/nginx.conf.example).

### Option 2: PaaS (Railway / Render / PythonAnywhere)

1. Push the repository to GitHub (`.env`, `instance/`, and `uploads/` are gitignored).
2. Provision a **MySQL 8** database and attach a persistent volume/disk at `/app/uploads` so posters and certificate PDFs persist across deploys.
3. Set `FLASK_APP=run.py`, `APP_ENV=production`, `SECRET_KEY`, `DATABASE_URL`, and `SESSION_COOKIE_SECURE=true`.
4. Run one-time initialization:
   ```bash
   flask db upgrade
   flask init-db
   flask create-admin
   ```

> **Note on HTTPS:** Modern browsers require HTTPS (outside `localhost`) for live webcam access (`getUserMedia`) in the coordinator QR scanner and for secure session cookies.

---

## Additional Documentation

- [Production deployment guide](docs/DEPLOYMENT.md)
- [Database backup and restoration](docs/BACKUP_RESTORE.md)
- [Administrator manual](docs/ADMINISTRATOR_MANUAL.md)
- [Coordinator and student guide](docs/COORDINATOR_STUDENT_GUIDE.md)
- [Security audit checklist](docs/SECURITY_AUDIT.md)
