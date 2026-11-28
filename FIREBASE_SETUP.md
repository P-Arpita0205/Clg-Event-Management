# Firebase Cloud Firestore Setup Guide

Campus Connect uses **Google Firebase Cloud Firestore** as its sole primary database via the Firebase Admin SDK for Python.

---

## 1. Create a Firebase Project & Enable Cloud Firestore

1. Open the [Firebase Console](https://console.firebase.google.com/).
2. Click **Add project** (or select your existing project), enter a name (e.g. `campus-connect`), and click **Continue**.
3. In the left sidebar, open **Build → Firestore Database**.
4. Click **Create database**, choose **Start in production mode** (the Flask backend accesses Firestore via the Admin SDK, so direct client-side browser access remains closed), select your nearest region (e.g. `asia-south1`), and click **Enable**.

---

## 2. Generate Service Account Credentials

1. Click the **Gear icon** next to **Project Overview** → **Project settings**.
2. Open the **Service accounts** tab.
3. Ensure **Python** is selected and click **Generate new private key** → **Generate key**.
4. Save the downloaded `.json` file inside the project root as `firebase-service-account.json` (or in a `secrets/` folder).

> **Security warning:** Never commit this `.json` file to Git. `.gitignore` already excludes `*firebase-adminsdk*.json`, `firebase-service-account*.json`, `serviceAccountKey*.json`, `credentials/*.json`, and `secrets/`.

---

## 3. Configure Environment Variables (`.env`)

Copy `.env.example` to `.env`:

```powershell
copy .env.example .env
```

Edit `.env` with your Firebase project details:

```env
FLASK_APP=run.py
FLASK_ENV=development
APP_ENV=development
SECRET_KEY=replace-with-a-long-random-secret
FIREBASE_PROJECT_ID=your-actual-firebase-project-id
FIREBASE_CREDENTIALS_PATH=firebase-service-account.json
SESSION_COOKIE_SECURE=false
```

- For PaaS/container environments where mounting a file is inconvenient, you may instead set `FIREBASE_CREDENTIALS_JSON` to the single-line JSON string of the service account key.
- In production (`APP_ENV=production`), set a strong `SECRET_KEY` (generated via `python -c "import secrets; print(secrets.token_urlsafe(48))"`) and `SESSION_COOKIE_SECURE=true` behind HTTPS.

---

## 4. Initialize Firestore Collections (Fresh Setup)

Install dependencies and seed the initial roles, departments, event categories, and campus resources:

```powershell
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
flask init-db
flask create-admin
```

*(For local testing only, `flask seed-demo` adds demo admin/coordinator/student accounts with password `CampusDemo123!`.)*

---

## 5. Migrate Existing SQLite Data (Optional)

If you have existing data in `instance/college_events.db` or `instance/campus.db`, run the non-destructive migration script:

1. **Preview first (dry run):**
   ```powershell
   python scripts/migrate_sqlite_to_firestore.py --source instance/college_events.db --dry-run
   ```
2. **Run the migration:**
   ```powershell
   python scripts/migrate_sqlite_to_firestore.py --source instance/college_events.db
   ```

- Preserves existing document IDs and relationships.
- Syncs `_counters/<collection>` so new records created in Flask get the next sequential ID without collisions.
- Skips already-migrated document IDs automatically so re-running is safe.
- Leaves your original `.db` file untouched as a backup.

---

## 6. Verify Live Firestore Connection

Run the verification script to confirm real read/write/update/delete operations against your Firebase project and print collection counts:

```powershell
python scripts/verify_firestore_live.py
```

Then start the Flask app:

```powershell
python run.py
```

Open `http://127.0.0.1:5000/health` — it should return `{"database": "firestore", "status": "ok"}`, and new users, events, registrations, volunteer applications, attendance records, certificates, and notifications will appear live in **Firebase Console → Firestore Database**.

---

## 7. Firestore Collections Created

`users`, `roles`, `departments`, `clubs`, `event_categories`, `events`, `event_registrations`, `volunteer_applications`, `volunteer_assignments`, `volunteer_tasks`, `attendance`, `certificates`, `notifications`, `feedback`, `event_galleries`, `volunteer_hours`, `event_budgets`, `event_expenses`, `resources`, `resource_bookings`, `student_interests`, and `_counters` (transactional ID sequence documents).
