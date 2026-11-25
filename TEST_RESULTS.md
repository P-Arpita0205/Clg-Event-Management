# Test Results (`pytest -v`)

## Command Executed
```powershell
pytest -v
```

## Database Configuration Used
- **URI:** `sqlite:///:memory:` (configured in `tests/test_app.py` via `TestConfig`)
- **CSRF:** `WTF_CSRF_ENABLED = False` globally in `TestConfig`, except `test_csrf_enabled_demo_login` which sets `app.config["WTF_CSRF_ENABLED"] = True`.
- **Persistence:** Ephemeral in-memory SQLite (discarded after each test fixture).

## Summary Statistics
- **Collected:** 35
- **Passed:** 35
- **Failed:** 0
- **Skipped:** 0
- **Duration:** 16.47s
- **Exit Code:** 0

## Verbatim Command Output Summary
```text
============================= test session starts =============================
platform win32 -- Python 3.10.0, pytest-8.4.2, pluggy-1.7.0
rootdir: C:\Users\user\OneDrive\Desktop\temp\college_event_management
configfile: pytest.ini
testpaths: tests
plugins: anyio-4.13.0, flask-1.3.0
collected 35 items

tests\test_app.py ...................................                    [100%]

============================= 35 passed in 16.47s =============================
```

## Test Coverage Breakdown (`tests/test_app.py`)
- 31 pre-existing functional, security, analytics, and CLI tests.
- 4 newly added authentication & RBAC tests:
  - `test_role_logins_redirect_to_own_dashboards`
  - `test_login_unknown_email_and_bad_password_stay_unauthenticated`
  - `test_unauthenticated_dashboard_access_redirects_to_login`
  - `test_cross_role_dashboard_authorization_and_logout_invalidation`

## MySQL Verification
- **Status:** **NOT TESTED** (no MySQL server or Docker available in the current environment).
