# Campus Connect — College Event & Volunteer Management System

Campus Connect is a role-based Flask web application backed by **Google Firebase Cloud Firestore** for managing college events, compulsory & optional student registrations, volunteer workflows, QR/unique-key attendance check-in, post-event verifiable PDF certificates, campus resource bookings, and analytics.

## Tech Stack

- **Backend:** Python 3.10+, Flask 3.1, Flask-Login, Flask-WTF (CSRF protection)
- **Database:** Google Firebase Cloud Firestore (`firebase-admin`)
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
│   ├── firebase_config.py   # Firebase Admin SDK initialization & Firestore client
│   ├── firestore_db.py      # Firestore DAL, transactions, atomic counters, batch writes & serialization
│   ├── firestore_memory.py  # In-memory Firestore backend for unit tests
│   ├── models.py            # Cloud Firestore domain models (21 collections) and event/attendance helpers
│   ├── decorators.py        # Role-based access control decorator
│   ├── forms.py             # Flask-WTF forms and validation
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
├── scripts/                 # Live Firestore verification (verify_firestore_live.py) & SQLite-to-Firestore migration (migrate_sqlite_to_firestore.py)
├── tests/                   # Pytest test suite (runs against InMemoryFirestoreClient)
├── .env.example             # Safe environment template (never commit .env or service account JSON)
├── FIREBASE_SETUP.md        # Step-by-step Firebase & Cloud Firestore setup guide
├── config.py                # Config & ProductionConfig
├── Dockerfile
├── docker-compose.yml
├── Procfile
├── requirements.txt
├── requirements-dev.txt
└── run.py
```

---

## Cloud Firestore Collections

Campus Connect uses **Google Firebase Cloud Firestore** as its sole primary database with transactional integer ID counters in `_counters`:

`roles`, `departments`, `clubs`, `event_categories`, `resources`, `users`, `events`, `event_registrations`, `volunteer_applications`, `volunteer_assignments`, `volunteer_tasks`, `attendance`, `certificates`, `notifications`, `feedback`, `event_galleries`, `volunteer_hours`, `event_budgets`, `event_expenses`, `resource_bookings`, `student_interests`

---

## Environment Variables

Copy `.env.example` to `.env` for local development. See [FIREBASE_SETUP.md](FIREBASE_SETUP.md) for creating your Firebase project and service account key. In production (`APP_ENV=production`), `create_app()` enforces a non-default `SECRET_KEY` and configured Firebase credentials.

> **Security notice:** `.env`, `firebase-service-account.json`, `*firebase-adminsdk*.json`, `serviceAccountKey*.json`, `instance/`, and `uploads/` are excluded in `.gitignore` and must never be committed to GitHub.

| Variable | Description | Example / Default |
|---|---|---|
| `FLASK_APP` | Flask entrypoint | `run.py` |
| `FLASK_ENV` | Flask environment | `development` |
| `APP_ENV` | App environment (`development` or `production`) | `development` |
| `SECRET_KEY` | Strong random secret key (32+ chars in production) | *(generate with `secrets.token_urlsafe(48)`)* |
| `FIREBASE_PROJECT_ID` | Google Firebase project ID | `your-firebase-project-id` |
| `FIREBASE_CREDENTIALS_PATH` | Path to service account JSON key (never commit) | `firebase-service-account.json` |
| `FIREBASE_CREDENTIALS_JSON` | Optional single-line service account JSON for PaaS/containers | *(set in host secret manager)* |
| `FIRESTORE_BACKEND` | `firestore` for live Cloud Firestore; `memory` for tests | `firestore` |
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

Configure `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_PATH`, and `FIRESTORE_BACKEND=firestore` in `.env` (see [FIREBASE_SETUP.md](FIREBASE_SETUP.md)), verify live Firestore connectivity, then initialize collections and run the app:

```powershell
python scripts/verify_firestore_live.py
flask init-db
flask create-admin
python run.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/verify_firestore_live.py
flask init-db
flask create-admin
python run.py
```

Open `http://127.0.0.1:5000` (or check `http://127.0.0.1:5000/health` for `{"database": "firestore", "status": "ok"}`).

To preview or migrate legacy SQLite records into Cloud Firestore without modifying the `.db` file:

```powershell
python scripts/migrate_sqlite_to_firestore.py --source instance/campus.db --dry-run
python scripts/migrate_sqlite_to_firestore.py --source instance/campus.db
```

### Optional Demo Data (Local Only)

```bash
flask seed-demo
```

This seeds idempotent demo accounts (password: `CampusDemo123!`) for `admin@college.edu`, `coordinator@college.edu`, and `student@college.edu` along with a sample event. **Never run `seed-demo` in production.**

For production admin creation, use:

```bash
flask create-admin
```

---

## Running Tests

The test suite runs against `InMemoryFirestoreClient` (`FIRESTORE_BACKEND=memory`) so tests execute offline without touching your live Cloud Firestore database:

```bash
pip install -r requirements-dev.txt
pytest -v
```

---

## Production Deployment

### Option 1: Docker / Container Hosting

Build and run the container with Cloud Firestore environment variables and persistent volume storage at `/app/uploads` for uploaded posters, galleries, and generated certificate PDFs:

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(48))")
export APP_ENV="production"
export FIRESTORE_BACKEND="firestore"
export FIREBASE_PROJECT_ID="your-firebase-project-id"
export FIREBASE_CREDENTIALS_JSON='{"type":"service_account",...}'
export SESSION_COOKIE_SECURE="true"

docker build -t campus-connect .
docker run -d -p 5000:5000 \
  -e APP_ENV -e SECRET_KEY -e FIRESTORE_BACKEND \
  -e FIREBASE_PROJECT_ID -e FIREBASE_CREDENTIALS_JSON \
  -e SESSION_COOKIE_SECURE \
  -v uploads_data:/app/uploads \
  campus-connect
```

Verify health at `/health` (returns `{"database": "firestore", "status": "ok"}`). Put Nginx with TLS/HTTPS in front using [deploy/nginx.conf.example](deploy/nginx.conf.example).

### Option 2: PaaS (Render / Railway / PythonAnywhere)

1. Push the repository to GitHub (`.env`, `firebase-service-account.json`, `instance/`, and `uploads/` are gitignored).
2. Attach a persistent disk at `/app/uploads` so posters and certificate PDFs persist across deploys.
3. Configure environment variables in your host's secret manager: `FLASK_APP=run.py`, `APP_ENV=production`, `SECRET_KEY`, `FIRESTORE_BACKEND=firestore`, `FIREBASE_PROJECT_ID`, `FIREBASE_CREDENTIALS_JSON` (or mounted `FIREBASE_CREDENTIALS_PATH`), and `SESSION_COOKIE_SECURE=true`.
4. Run one-time setup commands in the host shell:
   ```bash
   python scripts/verify_firestore_live.py
   flask init-db
   flask create-admin
   ```

> **Note on HTTPS:** Modern browsers require HTTPS (outside `localhost`) for live webcam access (`getUserMedia`) in the coordinator QR scanner and for secure session cookies.

---

## Additional Documentation

- [Firebase Cloud Firestore setup guide](FIREBASE_SETUP.md)
- [Production deployment guide](docs/DEPLOYMENT.md)
- [Database backup and restoration](docs/BACKUP_RESTORE.md)
- [Administrator manual](docs/ADMINISTRATOR_MANUAL.md)
- [Coordinator and student guide](docs/COORDINATOR_STUDENT_GUIDE.md)
- [Security audit checklist](docs/SECURITY_AUDIT.md)
