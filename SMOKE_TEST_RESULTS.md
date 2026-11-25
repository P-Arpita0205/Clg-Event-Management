# Smoke Test Results (`scripts/smoke_test_sqlite.py`)

## Command Executed
```powershell
$env:PYTHONPATH='.'
python scripts/smoke_test_sqlite.py
```

## Database Configuration Used
- **URI:** `sqlite:///:memory:` (set via `os.environ["DATABASE_URL"] = "sqlite:///:memory:"` in `scripts/smoke_test_sqlite.py`)
- **CSRF:** `WTF_CSRF_ENABLED = False`
- **Persistence:** Ephemeral in-memory SQLite; not a persistent database check.

## Summary Statistics
- **Total Checks:** 24
- **Passed:** 24
- **Failed:** 0
- **Exit Code:** 0

## Verbatim Output
```json
{"step": "unauthenticated access to admin dashboard", "passed": true, "url": "/admin/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fadmin%2F"}
{"step": "unauthenticated access to coordinator dashboard", "passed": true, "url": "/coordinator/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fcoordinator%2F"}
{"step": "unauthenticated access to student dashboard", "passed": true, "url": "/student/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fstudent%2F"}
{"step": "student login (bad password)", "passed": true, "status": 200, "expected": 200, "contains": "Invalid email or password."}
{"step": "session remains unauthenticated after bad password", "passed": true, "url": "/student/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fstudent%2F"}
{"step": "unknown email login", "passed": true, "status": 200, "expected": 200, "contains": "Invalid email or password."}
{"step": "admin login (correct password)", "passed": true, "status": 302, "expected": 302, "location": "/admin/"}
{"step": "admin accesses admin dashboard", "passed": true, "url": "/admin/", "status": 200, "expected": 200, "contains": "Administration overview"}
{"step": "admin accesses coordinator dashboard", "passed": true, "url": "/coordinator/", "status": 403, "expected": 403, "contains": null}
{"step": "admin accesses student dashboard", "passed": true, "url": "/student/", "status": 403, "expected": 403, "contains": null}
{"step": "admin logout", "passed": true, "status": 302, "expected": 302}
{"step": "admin access to own dashboard after logout", "passed": true, "url": "/admin/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fadmin%2F"}
{"step": "coordinator login (correct password)", "passed": true, "status": 302, "expected": 302, "location": "/coordinator/"}
{"step": "coordinator accesses admin dashboard", "passed": true, "url": "/admin/", "status": 403, "expected": 403, "contains": null}
{"step": "coordinator accesses coordinator dashboard", "passed": true, "url": "/coordinator/", "status": 200, "expected": 200, "contains": "Coordinator overview"}
{"step": "coordinator accesses student dashboard", "passed": true, "url": "/student/", "status": 403, "expected": 403, "contains": null}
{"step": "coordinator logout", "passed": true, "status": 302, "expected": 302}
{"step": "coordinator access to own dashboard after logout", "passed": true, "url": "/coordinator/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fcoordinator%2F"}
{"step": "student login (correct password)", "passed": true, "status": 302, "expected": 302, "location": "/student/"}
{"step": "student accesses admin dashboard", "passed": true, "url": "/admin/", "status": 403, "expected": 403, "contains": null}
{"step": "student accesses coordinator dashboard", "passed": true, "url": "/coordinator/", "status": 403, "expected": 403, "contains": null}
{"step": "student accesses student dashboard", "passed": true, "url": "/student/", "status": 200, "expected": 200, "contains": "Student overview"}
{"step": "student logout", "passed": true, "status": 302, "expected": 302}
{"step": "student access to own dashboard after logout", "passed": true, "url": "/student/", "status": 302, "expected": 302, "location": "/auth/login?next=%2Fstudent%2F"}
{"summary": {"total_checks": 24, "passed": 24, "failed": 0}}
```
