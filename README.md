# Campus Connect

Campus Connect is a modular Flask + MySQL college event and volunteer management platform.

## Phase 1 features

- Flask application factory and modular blueprints
- Role-based access for admin, coordinator, and student users
- Secure password hashing and Flask-Login sessions
- CSRF-protected login and registration forms
- SQLAlchemy models for users, roles, departments, and clubs
- Initial responsive dashboards
- Database-backed admin department statistics
- Flask-Migrate and Docker support
- Phase 1 automated tests

## Phase 2 features

- Event categories and event creation/editing
- Poster image uploads
- Coordinator event cancellation
- Admin event approval and rejection
- Public event search and category filtering
- Duplicate-safe event registration
- Registration deadline and capacity validation
- Participant lists
- Volunteer applications
- Coordinator approval, rejection, and role assignment
- Student registration and volunteer application histories

### Phase 2 workflow

1. Sign in as a coordinator and create an event.
2. Sign in as an admin and approve or reject the event.
3. Sign in as a student to browse, register, or apply to volunteer.
4. Sign in as the coordinator to review and assign approved volunteers.

## Phase 3 features

- Volunteer task creation and deadline tracking
- Student task status updates
- In-app task, registration, volunteer, and attendance notifications
- Unread notification counts and mark-as-read controls
- Unique QR attendance codes for registrations
- QR attendance validation with duplicate protection
- Manual coordinator attendance fallback
- Attendance reports
- Database-backed coordinator and student task/attendance statistics

## Phase 4 features

- Participation, volunteer, and event coordination PDF certificates
- Unique certificate IDs and QR verification codes
- Public valid/invalid certificate verification pages
- Certificate download and certificate history
- Duplicate certificate prevention
- Certificate availability notifications
- Chart.js analytics for event categories and event lifecycle status

## Phase 5 features

- Star-rating and suggestions event feedback
- Optional anonymous feedback submission
- Duplicate feedback prevention
- Coordinator feedback review and average ratings
- Admin department creation and deletion with usage protection
- Admin club creation and activation/deactivation
- Department-wise event filtering
- Month-by-month published event calendar

## Phase 6 features

- Event gallery uploads and public gallery pages
- Volunteer leaderboard based on recorded hours
- Coordinator volunteer-hours recording
- Student volunteer-hours history
- Event budgets and expense tracking
- Classroom, seminar hall, auditorium, and laboratory resources
- Resource booking with overlapping-time conflict detection
- Budget and resource database relationships

## Phase 7 features

- Rule-based event recommendations from interests, department, and participation history
- Student category-interest preferences
- Volunteer-role recommendations based on prior approved or rejected applications
- Rule-based event description drafts
- Feedback theme extraction using keyword groups
- No paid API, external AI service, or generative model dependency

## Phase 8 testing and deployment

- Consolidated pytest suite covers authentication, authorization, registration, capacity, attendance, certificates, feedback, resources, and rule-based recommendations
- `/health` provides a database connectivity check
- Production responses include security headers
- `flask seed-demo` creates idempotent demo accounts and one published event
- Demo account password: `CampusDemo123!`
- Demo accounts should never be enabled in a public production deployment

## Production deployment

1. Copy `.env.example` to `.env` and set a unique 32+ character `SECRET_KEY`.
2. Set `SESSION_COOKIE_SECURE=true` and serve the application behind HTTPS.
3. Configure `DATABASE_URL` for a managed MySQL 8 database.
4. Run `flask db upgrade`.
5. Run `flask init-db` for system categories and departments.
6. Use Gunicorn for the container entrypoint.

```powershell
docker compose up --build -d
docker compose exec web flask db upgrade
docker compose exec web flask init-db
```

## Phase 9 handover package

- [Production deployment guide](docs/DEPLOYMENT.md)
- [Database backup and restoration](docs/BACKUP_RESTORE.md)
- [Administrator manual](docs/ADMINISTRATOR_MANUAL.md)
- [Coordinator and student guide](docs/COORDINATOR_STUDENT_GUIDE.md)
- [Final testing report](docs/FINAL_TESTING_REPORT.md)
- [Known limitations](docs/KNOWN_LIMITATIONS.md)
- [Security audit checklist](docs/SECURITY_AUDIT.md)

## Local setup

### 1. Create an environment

```powershell
cd college_event_management
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Set `SECRET_KEY` and `DATABASE_URL` in `.env`. The default SQLite URL is used when `DATABASE_URL` is omitted.

### 2. Initialize a database

For MySQL, create a database and account, then set `DATABASE_URL=mysql+pymysql://user:password@localhost:3306/college_events`.

```powershell
flask db init
flask db migrate -m "Initial foundation schema"
flask db upgrade
flask init-db
flask run
```

Use `http://127.0.0.1:5000`.

### 3. Run tests

```powershell
pytest -q
```

## Docker setup

```powershell
$env:MYSQL_PASSWORD="use-a-local-password"
$env:MYSQL_ROOT_PASSWORD="use-a-root-password"
$env:SECRET_KEY="use-a-long-random-secret"
docker compose up --build
```

Initialize the database in the web container:

```powershell
docker compose exec web flask db upgrade
docker compose exec web flask init-db
```

## Security notes

- Never commit `.env`.
- Use a strong random `SECRET_KEY`.
- Use TLS and secure cookies in production.
- Run behind a reverse proxy and set `SESSION_COOKIE_SECURE=true`.
