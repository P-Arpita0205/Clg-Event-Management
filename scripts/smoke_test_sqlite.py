#!/usr/bin/env python
"""
SQLite smoke-test that exercises the real login/logout routes and checks
unauthenticated access, invalid logins, role-based dashboard access, and
cross-role denial using an ephemeral in-memory SQLite database.
"""

import json
import os
import sys

# Ensure the Flask app uses an in-memory SQLite DB before importing Config/app.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"

from app import create_app, db
from app.models import Department, EventCategory, Role, User


EXPECTED_HEADINGS = {
    "admin": "Administration overview",
    "coordinator": "Coordinator overview",
    "student": "Student overview",
}

DASHBOARD_ROUTES = {
    "admin": "/admin/",
    "coordinator": "/coordinator/",
    "student": "/student/",
}


def _create_user(app, role_name, email, password="StrongPass123!"):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        dept = Department.query.first()
        user = User(
            full_name=f"{role_name.title()} User",
            email=email,
            student_id=f"{role_name[:3].upper()}-{email.split('@')[0]}",
            role=role,
            department=dept,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def main():
    app = create_app()
    app.config.update(
        TESTING=True,
        WTF_CSRF_ENABLED=False,
    )

    with app.app_context():
        db.create_all()
        for name in ("admin", "coordinator", "student"):
            db.session.add(Role(name=name))
        db.session.add(Department(name="Computer Science", code="CSE"))
        for cat in ("Technical", "Cultural", "Sports"):
            db.session.add(EventCategory(name=cat))
        db.session.commit()

        _create_user(app, "admin", "admin@example.com")
        _create_user(app, "coordinator", "coord@example.com")
        _create_user(app, "student", "stud@example.com")

    client = app.test_client()
    results = []

    def login(email, pwd):
        return client.post(
            "/auth/login",
            data={"email": email, "password": pwd},
            follow_redirects=False,
        )

    def logout():
        return client.get("/auth/logout", follow_redirects=False)

    def record(step, passed, **details):
        entry = {"step": step, "passed": bool(passed), **details}
        results.append(entry)

    # 1. Unauthenticated access checks for all three dashboards
    for dash_role, url in DASHBOARD_ROUTES.items():
        resp = client.get(url, follow_redirects=False)
        loc = resp.headers.get("Location", "")
        ok = resp.status_code == 302 and "/auth/login" in loc
        record(
            f"unauthenticated access to {dash_role} dashboard",
            ok,
            url=url,
            status=resp.status_code,
            expected=302,
            location=loc,
        )

    # 2. Incorrect-password rejection & verify session stays unauthenticated
    bad_resp = login("stud@example.com", "WrongPassword")
    bad_ok = (
        bad_resp.status_code == 200
        and b"Invalid email or password." in bad_resp.data
    )
    record(
        "student login (bad password)",
        bad_ok,
        status=bad_resp.status_code,
        expected=200,
        contains="Invalid email or password.",
    )

    post_bad_dash = client.get("/student/", follow_redirects=False)
    post_bad_loc = post_bad_dash.headers.get("Location", "")
    record(
        "session remains unauthenticated after bad password",
        post_bad_dash.status_code == 302 and "/auth/login" in post_bad_loc,
        url="/student/",
        status=post_bad_dash.status_code,
        expected=302,
        location=post_bad_loc,
    )

    # 3. Unknown email rejection
    unknown_resp = login("unknown@example.com", "StrongPass123!")
    unknown_ok = (
        unknown_resp.status_code == 200
        and b"Invalid email or password." in unknown_resp.data
    )
    record(
        "unknown email login",
        unknown_ok,
        status=unknown_resp.status_code,
        expected=200,
        contains="Invalid email or password.",
    )

    # 4. Login, role-based dashboard access, cross-role denial, logout, and post-logout denial
    accounts = [
        ("admin", "admin@example.com"),
        ("coordinator", "coord@example.com"),
        ("student", "stud@example.com"),
    ]
    for role, email in accounts:
        login_resp = login(email, "StrongPass123!")
        login_loc = login_resp.headers.get("Location", "")
        expected_dash = DASHBOARD_ROUTES[role]
        record(
            f"{role} login (correct password)",
            login_resp.status_code == 302 and expected_dash in login_loc,
            status=login_resp.status_code,
            expected=302,
            location=login_loc,
        )

        for dash_role, url in DASHBOARD_ROUTES.items():
            resp = client.get(url, follow_redirects=False)
            allowed = role == dash_role
            expected_code = 200 if allowed else 403
            heading = EXPECTED_HEADINGS[dash_role] if allowed else None
            content_ok = (heading.encode() in resp.data) if allowed else True
            record(
                f"{role} accesses {dash_role} dashboard",
                resp.status_code == expected_code and content_ok,
                url=url,
                status=resp.status_code,
                expected=expected_code,
                contains=heading,
            )

        logout_resp = logout()
        record(
            f"{role} logout",
            logout_resp.status_code == 302,
            status=logout_resp.status_code,
            expected=302,
        )

        after_logout = client.get(expected_dash, follow_redirects=False)
        after_loc = after_logout.headers.get("Location", "")
        record(
            f"{role} access to own dashboard after logout",
            after_logout.status_code == 302 and "/auth/login" in after_loc,
            url=expected_dash,
            status=after_logout.status_code,
            expected=302,
            location=after_loc,
        )

    for r in results:
        print(json.dumps(r, ensure_ascii=False))

    total_checks = len(results)
    passed_checks = sum(1 for r in results if r["passed"])
    failed_checks = total_checks - passed_checks
    summary = {
        "total_checks": total_checks,
        "passed": passed_checks,
        "failed": failed_checks,
    }
    print(json.dumps({"summary": summary}, ensure_ascii=False))

    sys.exit(0 if failed_checks == 0 else 1)


if __name__ == "__main__":
    main()
