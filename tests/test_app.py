import pytest
import re

from app import create_app, db
from app.models import (
    Department,
    Event,
    EventCategory,
    EventRegistration,
    Role,
    User,
    VolunteerApplication,
    VolunteerAssignment,
    VolunteerTask,
    Attendance,
    Notification,
    Certificate,
    Feedback,
    Club,
    Resource,
    ResourceBooking,
    VolunteerHours,
    EventBudget,
    StudentInterest,
)
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from config import Config


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


@pytest.fixture()
def app():
    application = create_app(TestConfig)
    with application.app_context():
        db.create_all()
        for role_name in ("admin", "coordinator", "student"):
            db.session.add(Role(name=role_name))
        department = Department(name="Computer Science", code="CSE")
        db.session.add(department)
        for name in ("Technical", "Cultural", "Sports", "Workshop", "Seminar", "Fest"):
            db.session.add(EventCategory(name=name))
        db.session.commit()
        yield application
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def create_user(app, role_name, email="person@college.edu", password="SecurePass123!"):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        department = Department.query.first()
        user = User(
            full_name="Test Person",
            email=email,
            student_id="STU-" + email.split("@")[0],
            role=role,
            department=department,
        )
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


def test_homepage(client):
    response = client.get("/")
    assert response.status_code == 200
    assert b"Campus Connect" in response.data


def test_student_registration_and_login(client, app):
    admin_id = create_user(app, "admin", "regadmin@college.edu")
    with app.app_context():
        department_id = Department.query.first().id
    response = client.post(
        "/auth/register",
        data={
            "full_name": "Alex Student",
            "email": "alex@college.edu",
            "student_id": "CSE2026001",
            "phone": "+91 98765 43210",
            "password": "StrongPassword123!",
            "confirm_password": "StrongPassword123!",
            "department_id": department_id,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"sent to the administrator for approval" in response.data

    with app.app_context():
        student = User.query.filter_by(email="alex@college.edu").first()
        assert student is not None
        assert student.is_active is False
        student_id = student.id
        assert Notification.query.filter_by(
            user_id=admin_id,
            title="New student sign-up request",
        ).count() == 1

    # Cannot sign in before admin approval
    pending_login = client.post(
        "/auth/login",
        data={"email": "alex@college.edu", "password": "StrongPassword123!"},
        follow_redirects=True,
    )
    assert pending_login.status_code == 200
    assert b"pending administrator approval" in pending_login.data

    # Admin approves the sign-up request
    client.post(
        "/auth/login",
        data={"email": "regadmin@college.edu", "password": "SecurePass123!"},
        follow_redirects=False,
    )
    approve_resp = client.post(f"/admin/students/{student_id}/approve", follow_redirects=True)
    assert approve_resp.status_code == 200
    with app.app_context():
        assert db.session.get(User, student_id).is_active is True

    # Student can now log in
    client.get("/auth/logout", follow_redirects=False)
    login_resp = client.post(
        "/auth/login",
        data={"email": "alex@college.edu", "password": "StrongPassword123!"},
        follow_redirects=True,
    )
    assert login_resp.status_code == 200
    assert b"Welcome, Alex" in login_resp.data


def test_login_rejects_bad_password(client, app):
    create_user(app, "student")
    response = client.post(
        "/auth/login",
        data={"email": "person@college.edu", "password": "wrong-password"},
    )
    assert response.status_code == 200
    assert b"Invalid email or password" in response.data


def test_student_cannot_access_admin_dashboard(client, app):
    user_id = create_user(app, "student")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response = client.get("/admin/", follow_redirects=False)
    assert response.status_code == 403


def test_admin_dashboard_uses_database_counts(client, app):
    user_id = create_user(app, "admin", "admin@college.edu")
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True
    response = client.get("/admin/")
    assert response.status_code == 200
    assert b"Administration overview" in response.data


def create_event(app, coordinator_id, status="published", capacity=2, ended=False):
    with app.app_context():
        coordinator = db.session.get(User, coordinator_id)
        department = Department.query.first()
        category = EventCategory.query.first()
        event_date = (
            date.today() - timedelta(days=1)
            if ended
            else date.today() + timedelta(days=14)
        )
        deadline = (
            datetime.now() - timedelta(days=2)
            if ended
            else datetime.now() + timedelta(days=7)
        )
        event = Event(
            title="Innovation Summit",
            slug="innovation-summit",
            description="A complete campus innovation and technology summit.",
            category=category,
            coordinator=coordinator,
            department=department,
            venue="Main Auditorium",
            organizer="Computer Science Department",
            event_date=event_date,
            start_time=time(10, 0),
            end_time=time(13, 0),
            registration_deadline=deadline,
            capacity=capacity,
            volunteer_requirement=5,
            status=status,
        )
        db.session.add(event)
        db.session.commit()
        return event.id


def login_as(client, user_id):
    with client.session_transaction() as session:
        session["_user_id"] = str(user_id)
        session["_fresh"] = True


def test_admin_can_view_and_publish_event(client, app):
    admin_id = create_user(app, "admin", "admin2@college.edu")
    coordinator_id = create_user(app, "coordinator", "coordinator@college.edu")
    event_id = create_event(app, coordinator_id, status="draft")
    login_as(client, admin_id)

    response = client.post(
        f"/events/{event_id}/approve",
        data={"note": "Approved for campus publication"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Event, event_id).status == "published"


def test_student_registration_is_duplicate_and_capacity_safe(client, app):
    coordinator_id = create_user(app, "coordinator", "coordinator2@college.edu")
    student_id = create_user(app, "student", "student@college.edu")
    event_id = create_event(app, coordinator_id, capacity=1)
    login_as(client, student_id)

    first = client.post(f"/events/{event_id}/register", follow_redirects=True)
    duplicate = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert first.status_code == 200
    assert duplicate.status_code == 200
    with app.app_context():
        assert EventRegistration.query.filter_by(event_id=event_id, student_id=student_id).count() == 1


def test_capacity_prevents_second_student_registration(client, app):
    coordinator_id = create_user(app, "coordinator", "coordinator3@college.edu")
    first_id = create_user(app, "student", "first@college.edu")
    second_id = create_user(app, "student", "second@college.edu")
    event_id = create_event(app, coordinator_id, capacity=1)

    login_as(client, first_id)
    assert client.post(f"/events/{event_id}/register").status_code == 302
    login_as(client, second_id)
    response = client.post(f"/events/{event_id}/register", follow_redirects=True)
    assert b"reached capacity" in response.data


def test_coordinator_can_approve_and_assign_volunteer(client, app):
    coordinator_id = create_user(app, "coordinator", "coordinator4@college.edu")
    student_id = create_user(app, "student", "volunteer@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        application = VolunteerApplication(
            event_id=event_id,
            student_id=student_id,
            availability="Saturday all day",
            preferred_role="Technical Support",
            status="pending",
        )
        db.session.add(application)
        db.session.commit()
        application_id = application.id

    login_as(client, coordinator_id)
    approved = client.post(f"/events/applications/{application_id}/approve", follow_redirects=True)
    assert approved.status_code == 200
    assigned = client.post(
        f"/events/applications/{application_id}/assign",
        data={"volunteer_role": "Technical Support", "responsibilities": "Support demo stations"},
        follow_redirects=True,
    )
    assert assigned.status_code == 200
    with app.app_context():
        application = db.session.get(VolunteerApplication, application_id)
        assert application.status == "approved"
        assert application.assignment is not None
        assert application.assignment.volunteer_role == "Technical Support"


def test_task_assignment_updates_student_status_and_notification(client, app):
    coordinator_id = create_user(app, "coordinator", "taskcoord@college.edu")
    student_id = create_user(app, "student", "taskstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        application = VolunteerApplication(
            event_id=event_id,
            student_id=student_id,
            availability="Weekend",
            preferred_role="Stage Management",
            status="approved",
        )
        db.session.add(application)
        db.session.flush()
        assignment = VolunteerAssignment(
            application_id=application.id,
            volunteer_role="Stage Management",
        )
        db.session.add(assignment)
        db.session.commit()
        assignment_id = assignment.id

    login_as(client, coordinator_id)
    response = client.post(
        f"/tasks/event/{event_id}",
        data={
            "assignment_id": assignment_id,
            "title": "Prepare stage cues",
            "description": "Review the stage handover list.",
            "deadline": "2026-12-01T18:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        task = VolunteerTask.query.one()
        assert task.status == "assigned"
        assert Notification.query.filter_by(
            user_id=student_id,
            title="New task assigned",
        ).count() == 1
        task_id = task.id

    deadline_update = client.post(
        f"/tasks/{task_id}/deadline",
        data={"deadline_date": "2026-12-05", "deadline_time": "14:30"},
        follow_redirects=True,
    )
    assert deadline_update.status_code == 200
    with app.app_context():
        assert db.session.get(VolunteerTask, task_id).deadline == datetime(2026, 12, 5, 14, 30)

    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={
            "email": "taskstudent@college.edu",
            "password": "SecurePass123!",
        },
    )
    response = client.post(
        f"/tasks/{task_id}/status",
        data={"status": "completed"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(VolunteerTask, task_id).status == "completed"


def test_qr_attendance_is_recorded_once(client, app):
    coordinator_id = create_user(app, "coordinator", "qrcoord@college.edu")
    student_id = create_user(app, "student", "qrstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        registration = EventRegistration(
            event_id=event_id,
            student_id=student_id,
            status="confirmed",
        )
        db.session.add(registration)
        db.session.commit()
        token = registration.qr_token

    login_as(client, coordinator_id)
    first = client.get(f"/attendance/validate/{token}")
    duplicate = client.get(f"/attendance/validate/{token}")
    assert first.status_code == 200
    assert b"Attendance recorded successfully" in first.data
    assert b"already been recorded" in duplicate.data
    with app.app_context():
        assert Attendance.query.filter_by(
            event_id=event_id,
            student_id=student_id,
        ).count() == 1


def test_manual_attendance_is_duplicate_safe(client, app):
    coordinator_id = create_user(app, "coordinator", "manualcoord@college.edu")
    student_id = create_user(app, "student", "manualstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        db.session.add(
            EventRegistration(
                event_id=event_id,
                student_id=student_id,
                status="confirmed",
            )
        )
        db.session.commit()

    login_as(client, coordinator_id)
    client.post(
        f"/attendance/event/{event_id}",
        data={"student_id": student_id},
        follow_redirects=True,
    )
    client.post(
        f"/attendance/event/{event_id}",
        data={"student_id": student_id},
        follow_redirects=True,
    )
    with app.app_context():
        records = Attendance.query.filter_by(
            event_id=event_id,
            student_id=student_id,
        ).all()
        assert len(records) == 1
        assert records[0].method == "manual"


def test_notification_mark_as_read(client, app):
    student_id = create_user(app, "student", "notify@college.edu")
    with app.app_context():
        item = Notification(
            user_id=student_id,
            title="Campus update",
            message="A scheduled event has changed.",
        )
        db.session.add(item)
        db.session.commit()
        notification_id = item.id

    login_as(client, student_id)
    response = client.post(
        f"/notifications/read/{notification_id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        assert db.session.get(Notification, notification_id).is_read is True


def test_participant_certificate_issuance_download_and_verification(client, app):
    admin_id = create_user(app, "admin", "certadmin@college.edu")
    coordinator_id = create_user(app, "coordinator", "certcoord@college.edu")
    student_id = create_user(app, "student", "certstudent@college.edu")
    event_id = create_event(app, coordinator_id, ended=True)
    with app.app_context():
        registration = EventRegistration(
            event_id=event_id,
            student_id=student_id,
            status="confirmed",
        )
        db.session.add(registration)
        db.session.flush()
        db.session.add(
            Attendance(
                event_id=event_id,
                student_id=student_id,
                registration_id=registration.id,
                method="qr",
            )
        )
        db.session.commit()

    login_as(client, coordinator_id)
    issue = client.post(
        f"/certificates/issue/participant/{event_id}/{student_id}",
        follow_redirects=True,
    )
    assert issue.status_code == 200

    with app.app_context():
        certificate = Certificate.query.one()
        assert certificate.certificate_id.startswith("CPC-")
        assert certificate.recipient_id == student_id
        certificate_id = certificate.certificate_id
        certificate_row_id = certificate.id
        assert certificate.pdf_path

    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={
            "email": "certstudent@college.edu",
            "password": "SecurePass123!",
        },
    )
    download = client.get(f"/certificates/download/{certificate_row_id}")
    assert download.status_code == 200
    assert download.mimetype == "application/pdf"

    public = client.get(f"/certificates/verify/{certificate_id}")
    assert public.status_code == 200
    assert b"Valid certificate" in public.data


def test_certificate_duplicate_is_prevented(client, app):
    coordinator_id = create_user(app, "coordinator", "dupcoord@college.edu")
    student_id = create_user(app, "student", "dupstudent@college.edu")
    event_id = create_event(app, coordinator_id, ended=True)
    with app.app_context():
        registration = EventRegistration(
            event_id=event_id,
            student_id=student_id,
            status="confirmed",
        )
        db.session.add(registration)
        db.session.flush()
        db.session.add(
            Attendance(
                event_id=event_id,
                student_id=student_id,
                registration_id=registration.id,
                method="qr",
            )
        )
        db.session.commit()

    login_as(client, coordinator_id)
    client.post(
        f"/certificates/issue/participant/{event_id}/{student_id}",
        follow_redirects=True,
    )
    client.post(
        f"/certificates/issue/participant/{event_id}/{student_id}",
        follow_redirects=True,
    )
    with app.app_context():
        assert Certificate.query.filter_by(
            recipient_id=student_id,
            event_id=event_id,
            certificate_type="participation",
        ).count() == 1


def test_admin_analytics_uses_database_values(client, app):
    admin_id = create_user(app, "admin", "analyticsadmin@college.edu")
    coordinator_id = create_user(app, "coordinator", "analyticscoord@college.edu")
    create_event(app, coordinator_id)
    login_as(client, admin_id)
    response = client.get("/analytics/admin")
    assert response.status_code == 200
    assert b"Events by category" in response.data


def test_student_can_submit_feedback_and_duplicate_is_prevented(client, app):
    coordinator_id = create_user(app, "coordinator", "feedbackcoord@college.edu")
    student_id = create_user(app, "student", "feedbackstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    login_as(client, student_id)

    first = client.post(
        f"/feedback/event/{event_id}",
        data={"rating": "5", "suggestions": "Excellent event", "is_anonymous": "on"},
        follow_redirects=True,
    )
    second = client.post(
        f"/feedback/event/{event_id}",
        data={"rating": "4", "suggestions": "Second attempt"},
        follow_redirects=True,
    )
    assert first.status_code == 200
    assert second.status_code == 200
    with app.app_context():
        assert Feedback.query.filter_by(event_id=event_id).count() == 1
        item = Feedback.query.filter_by(event_id=event_id).first()
        assert item.rating == 5
        assert item.is_anonymous is True


def test_feedback_average_and_coordinator_review(client, app):
    coordinator_id = create_user(app, "coordinator", "reviewcoord@college.edu")
    student_id = create_user(app, "student", "reviewstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        db.session.add_all([
            Feedback(event_id=event_id, student_id=student_id, rating=4, suggestions="Good"),
        ])
        db.session.commit()

    login_as(client, coordinator_id)
    response = client.get(f"/feedback/event/{event_id}/review")
    assert response.status_code == 200
    assert b"4.0" in response.data
    assert b"Good" in response.data


def test_admin_can_create_department_and_club(client, app):
    admin_id = create_user(app, "admin", "communityadmin@college.edu")
    login_as(client, admin_id)

    department = client.post(
        "/departments/create",
        data={"name": "Physics", "code": "PHY"},
        follow_redirects=True,
    )
    club = client.post(
        "/clubs/create",
        data={"name": "Robotics Club", "description": "Build and compete"},
        follow_redirects=True,
    )
    assert department.status_code == 200
    assert club.status_code == 200
    with app.app_context():
        assert Department.query.filter_by(code="PHY").count() == 1
        assert Club.query.filter_by(name="Robotics Club").count() == 1


def test_calendar_and_department_filter(client, app):
    coordinator_id = create_user(app, "coordinator", "calendarcoord@college.edu")
    event_id = create_event(app, coordinator_id)
    calendar = client.get("/calendar")
    assert calendar.status_code == 200
    assert b"Published events" in calendar.data
    assert b'id="sidebar"' not in calendar.data

    client.post(
        "/auth/login",
        data={"email": "calendarcoord@college.edu", "password": "SecurePass123!"},
        follow_redirects=False,
    )
    auth_calendar = client.get("/calendar")
    assert auth_calendar.status_code == 200
    assert b"Published events" in auth_calendar.data
    assert b'id="sidebar"' in auth_calendar.data

    with app.app_context():
        department_id = Department.query.first().id
    filtered = client.get(f"/events/?department={department_id}")
    assert filtered.status_code == 200
    assert b"Innovation Summit" in filtered.data


def test_resource_booking_conflict_is_detected(client, app):
    admin_id = create_user(app, "admin", "resourceadmin@college.edu")
    coordinator_id = create_user(app, "coordinator", "bookingcoord@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        resource = Resource(
            name="Main Seminar Hall",
            resource_type="Seminar Hall",
            capacity=200,
            is_active=True,
        )
        db.session.add(resource)
        db.session.flush()
        db.session.add(
            ResourceBooking(
                resource_id=resource.id,
                event_id=event_id,
                requester_id=admin_id,
                purpose="Existing booking",
                booking_date=date.today(),
                start_time=time(10, 0),
                end_time=time(12, 0),
                status="confirmed",
            )
        )
        db.session.commit()
        resource_id = resource.id

    login_as(client, coordinator_id)
    response = client.post(
        "/resources/book",
        data={
            "resource_id": str(resource_id),
            "event_id": str(event_id),
            "purpose": "Overlapping booking",
            "booking_date": date.today().isoformat(),
            "start_time": "11:00",
            "end_time": "13:00",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"already booked" in response.data


def test_coordinator_budget_and_expense_tracking(client, app):
    coordinator_id = create_user(app, "coordinator", "budgetcoord@college.edu")
    event_id = create_event(app, coordinator_id)
    login_as(client, coordinator_id)

    budget_response = client.post(
        f"/budget/event/{event_id}",
        data={
            "form_type": "budget",
            "allocated_amount": "5000",
        },
        follow_redirects=True,
    )
    expense_response = client.post(
        f"/budget/event/{event_id}",
        data={
            "form_type": "expense",
            "category": "Printing",
            "expense_date": date.today().isoformat(),
            "amount": "750",
            "description": "Event banners",
        },
        follow_redirects=True,
    )
    assert budget_response.status_code == 200
    assert expense_response.status_code == 200
    with app.app_context():
        budget = EventBudget.query.filter_by(event_id=event_id).first()
        assert budget is not None
        assert Decimal(str(budget.allocated_amount)) == Decimal("5000")
        assert len(budget.expenses) == 1
        assert Decimal(str(budget.expenses[0].amount)) == Decimal("750")


def test_volunteer_hours_recording_and_leaderboard(client, app):
    coordinator_id = create_user(app, "coordinator", "hourscoord@college.edu")
    student_id = create_user(app, "student", "hoursstudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        application = VolunteerApplication(
            event_id=event_id,
            student_id=student_id,
            availability="All day",
            preferred_role="Technical Support",
            status="approved",
        )
        db.session.add(application)
        db.session.commit()

    login_as(client, coordinator_id)
    response = client.post(
        "/volunteer-hours",
        data={
            "event_id": str(event_id),
            "student_id": str(student_id),
            "hours": "6.5",
            "note": "Setup and support",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    with app.app_context():
        hours = VolunteerHours.query.filter_by(
            event_id=event_id,
            student_id=student_id,
        ).one()
        assert Decimal(str(hours.hours)) == Decimal("6.50")

    leaderboard = client.get("/leaderboard")
    assert leaderboard.status_code == 200
    assert b"6.50" in leaderboard.data or b"6.5" in leaderboard.data


def test_student_interest_and_event_recommendation(client, app):
    student_id = create_user(app, "student", "interest@college.edu")
    coordinator_id = create_user(app, "coordinator", "interestcoord@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        category = db.session.get(Event, event_id).category
        category_id = category.id

    login_as(client, student_id)
    response = client.post(
        "/assistance/interests",
        data={"category_ids": str(category_id)},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Recommended for you" in response.data
    with app.app_context():
        assert StudentInterest.query.filter_by(
            student_id=student_id,
            category_id=category_id,
        ).count() == 1


def test_rule_based_volunteer_role_recommendation(client, app):
    student_id = create_user(app, "student", "role@college.edu")
    coordinator_id = create_user(app, "coordinator", "rolecoord@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        db.session.add(
            VolunteerApplication(
                event_id=event_id,
                student_id=student_id,
                availability="Saturday",
                preferred_role="Technical Support",
                status="approved",
            )
        )
        db.session.commit()

    login_as(client, student_id)
    response = client.get(f"/assistance/volunteer-role/{event_id}")
    assert response.status_code == 200
    assert b"Technical Support" in response.data


def test_rule_based_feedback_theme_analysis(client, app):
    coordinator_id = create_user(app, "coordinator", "themecoord@college.edu")
    student_id = create_user(app, "student", "themestudent@college.edu")
    event_id = create_event(app, coordinator_id)
    with app.app_context():
        db.session.add(
            Feedback(
                event_id=event_id,
                student_id=student_id,
                rating=3,
                suggestions="The projector and sound had technical problems.",
            )
        )
        db.session.commit()

    login_as(client, coordinator_id)
    response = client.get(f"/assistance/feedback-analysis/{event_id}")
    assert response.status_code == 200
    assert b"Technical quality" in response.data


def test_health_endpoint_and_security_headers(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json["status"] == "ok"
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"


def test_secure_error_pages(client):
    not_found = client.get("/a-page-that-does-not-exist")
    forbidden = client.get("/admin/")
    assert not_found.status_code == 404
    assert b"Page not found" in not_found.data
    assert forbidden.status_code in (403, 302)


def test_demo_student_login_redirects_to_dashboard(client, app):
    runner = app.test_cli_runner()
    seed = runner.invoke(args=["seed-demo"])
    assert seed.exit_code == 0
    response = client.post(
        "/auth/login",
        data={
            "email": "student@college.edu",
            "password": "CampusDemo123!",
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Student overview" in response.data


def test_csrf_enabled_demo_login(client, app):
    app.config["WTF_CSRF_ENABLED"] = True
    runner = app.test_cli_runner()
    runner.invoke(args=["seed-demo"])
    login_page = client.get("/auth/login")
    with client.session_transaction() as session:
        token = session.get("_csrf_token") or session.get("csrf_token")
    html = login_page.get_data(as_text=True)
    match = re.search(r'name="csrf_token"[^>]*value="([^"]+)', html)
    assert match
    token = match.group(1)
    assert token
    response = client.post(
        "/auth/login",
        data={
            "email": "student@college.edu",
            "password": "CampusDemo123!",
            "csrf_token": token,
        },
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert b"Student overview" in response.data


def test_demo_seed_command(app):
    runner = app.test_cli_runner()
    first = runner.invoke(args=["seed-demo"])
    second = runner.invoke(args=["seed-demo"])
    assert first.exit_code == 0
    assert second.exit_code == 0
    with app.app_context():
        assert User.query.filter_by(email="admin@college.edu").count() == 1
        assert User.query.filter_by(email="coordinator@college.edu").count() == 1
        assert User.query.filter_by(email="student@college.edu").count() == 1
        assert Event.query.filter_by(title="Campus Innovation Expo").count() == 1


def test_role_logins_redirect_to_own_dashboards(client, app):
    accounts = [
        ("admin", "admin_auth@college.edu", "/admin/", b"Administration overview"),
        ("coordinator", "coord_auth@college.edu", "/coordinator/", b"Coordinator overview"),
        ("student", "student_auth@college.edu", "/student/", b"Student overview"),
    ]
    for role_name, email, expected_path, expected_text in accounts:
        create_user(app, role_name, email)
        resp = client.post(
            "/auth/login",
            data={"email": email, "password": "SecurePass123!"},
            follow_redirects=False,
        )
        assert resp.status_code == 302
        assert expected_path in resp.headers["Location"]

        dash = client.get(expected_path, follow_redirects=False)
        assert dash.status_code == 200
        assert expected_text in dash.data

        logout_resp = client.get("/auth/logout", follow_redirects=False)
        assert logout_resp.status_code == 302


def test_login_unknown_email_and_bad_password_stay_unauthenticated(client, app):
    create_user(app, "student", "valid_student@college.edu")
    for email, password in [
        ("unknown_user@college.edu", "SecurePass123!"),
        ("valid_student@college.edu", "WrongPassword!"),
    ]:
        resp = client.post(
            "/auth/login",
            data={"email": email, "password": password},
            follow_redirects=False,
        )
        assert resp.status_code == 200
        assert b"Invalid email or password." in resp.data
        dash = client.get("/student/", follow_redirects=False)
        assert dash.status_code == 302
        assert "/auth/login" in dash.headers["Location"]


def test_unauthenticated_dashboard_access_redirects_to_login(client):
    for path in ("/admin/", "/coordinator/", "/student/"):
        resp = client.get(path, follow_redirects=False)
        assert resp.status_code == 302
        assert "/auth/login" in resp.headers["Location"]


def test_cross_role_dashboard_authorization_and_logout_invalidation(client, app):
    accounts = [
        ("admin", "rbac_admin@college.edu"),
        ("coordinator", "rbac_coord@college.edu"),
        ("student", "rbac_student@college.edu"),
    ]
    for role_name, email in accounts:
        create_user(app, role_name, email)

    dashboards = {
        "admin": ("/admin/", b"Administration overview"),
        "coordinator": ("/coordinator/", b"Coordinator overview"),
        "student": ("/student/", b"Student overview"),
    }

    for role_name, email in accounts:
        login_resp = client.post(
            "/auth/login",
            data={"email": email, "password": "SecurePass123!"},
            follow_redirects=False,
        )
        assert login_resp.status_code == 302

        for target_role, (path, heading) in dashboards.items():
            resp = client.get(path, follow_redirects=False)
            if role_name == target_role:
                assert resp.status_code == 200
                assert heading in resp.data
            else:
                assert resp.status_code == 403

        logout_resp = client.get("/auth/logout", follow_redirects=False)
        assert logout_resp.status_code == 302
        own_path, _ = dashboards[role_name]
        after_logout = client.get(own_path, follow_redirects=False)
        assert after_logout.status_code == 302
        assert "/auth/login" in after_logout.headers["Location"]


def test_admin_can_view_and_toggle_students(client, app):
    admin_id = create_user(app, "admin", "students_admin@college.edu")
    student_id = create_user(app, "student", "listed_student@college.edu")

    login_as(client, student_id)
    forbidden = client.get("/admin/students", follow_redirects=False)
    assert forbidden.status_code == 403

    client.get("/auth/logout", follow_redirects=False)
    client.post(
        "/auth/login",
        data={"email": "students_admin@college.edu", "password": "SecurePass123!"},
        follow_redirects=False,
    )
    page = client.get("/admin/students")
    assert page.status_code == 200
    assert b"listed_student@college.edu" in page.data

    toggled = client.post(f"/admin/students/{student_id}/toggle", follow_redirects=True)
    assert toggled.status_code == 200
    with app.app_context():
        assert db.session.get(User, student_id).is_active is False


def test_coordinator_profile_hides_volunteer_hours(client, app):
    coordinator_id = create_user(app, "coordinator", "nohours_coord@college.edu")
    login_as(client, coordinator_id)
    resp = client.get("/coordinator/")
    assert resp.status_code == 200
    assert b"Coordinator overview" in resp.data
    assert b"Record volunteer hours" not in resp.data
    assert b"/volunteer-hours" not in resp.data


def test_certificates_require_event_ended_and_qr_attendance(client, app):
    coordinator_id = create_user(app, "coordinator", "gatecoord@college.edu")
    participant_id = create_user(app, "student", "gatepart@college.edu")
    volunteer_id = create_user(app, "student", "gatevol@college.edu")
    active_event_id = create_event(app, coordinator_id, ended=False)

    with app.app_context():
        reg = EventRegistration(
            event_id=active_event_id,
            student_id=participant_id,
            status="confirmed",
        )
        vol_app = VolunteerApplication(
            event_id=active_event_id,
            student_id=volunteer_id,
            availability="All day",
            preferred_role="Registration Desk",
            status="approved",
        )
        db.session.add_all([reg, vol_app])
        db.session.flush()
        db.session.add_all([
            Attendance(
                event_id=active_event_id,
                student_id=participant_id,
                registration_id=reg.id,
                method="qr",
            ),
            Attendance(
                event_id=active_event_id,
                student_id=volunteer_id,
                volunteer_application_id=vol_app.id,
                method="qr",
            ),
        ])
        db.session.commit()

    login_as(client, coordinator_id)
    part_before = client.post(
        f"/certificates/issue/participant/{active_event_id}/{participant_id}",
        follow_redirects=True,
    )
    vol_before = client.post(
        f"/certificates/issue/volunteer/{active_event_id}/{volunteer_id}",
        follow_redirects=True,
    )
    assert part_before.status_code == 200
    assert vol_before.status_code == 200
    assert b"after the event has ended" in part_before.data
    assert b"after the event has ended" in vol_before.data
    with app.app_context():
        assert Certificate.query.count() == 0

        # Move event date into the past, but replace participant attendance with manual and remove volunteer attendance
        event = db.session.get(Event, active_event_id)
        event.event_date = date.today() - timedelta(days=1)
        Attendance.query.filter_by(event_id=active_event_id, student_id=participant_id).update({"method": "manual"})
        Attendance.query.filter_by(event_id=active_event_id, student_id=volunteer_id).delete()
        db.session.commit()

    part_manual = client.post(
        f"/certificates/issue/participant/{active_event_id}/{participant_id}",
        follow_redirects=True,
    )
    vol_missing = client.post(
        f"/certificates/issue/volunteer/{active_event_id}/{volunteer_id}",
        follow_redirects=True,
    )
    assert b"QR code attendance must be scanned" in part_manual.data
    assert b"QR code attendance must be scanned" in vol_missing.data
    with app.app_context():
        assert Certificate.query.count() == 0


def test_respective_certificates_after_event_ends_with_qr_attendance(client, app):
    coordinator_id = create_user(app, "coordinator", "respcoord@college.edu")
    student_a_id = create_user(app, "student", "part_qr@college.edu")
    student_b_id = create_user(app, "student", "vol_qr@college.edu")
    student_c_id = create_user(app, "student", "part_manual@college.edu")
    student_d_id = create_user(app, "student", "vol_none@college.edu")
    event_id = create_event(app, coordinator_id, capacity=10, ended=True)

    with app.app_context():
        reg_a = EventRegistration(event_id=event_id, student_id=student_a_id, status="confirmed")
        reg_c = EventRegistration(event_id=event_id, student_id=student_c_id, status="confirmed")
        app_b = VolunteerApplication(
            event_id=event_id,
            student_id=student_b_id,
            preferred_role="Technical Support",
            status="approved",
        )
        app_d = VolunteerApplication(
            event_id=event_id,
            student_id=student_d_id,
            preferred_role="Stage Management",
            status="approved",
        )
        db.session.add_all([reg_a, reg_c, app_b, app_d])
        db.session.flush()
        db.session.add(
            Attendance(
                event_id=event_id,
                student_id=student_c_id,
                registration_id=reg_c.id,
                method="manual",
            )
        )
        db.session.commit()
        reg_a_token = reg_a.qr_token
        app_b_id = app_b.id
        app_b_token = app_b.qr_token

    # Student B fetches volunteer QR code image
    login_as(client, student_b_id)
    vol_qr_img = client.get(f"/attendance/qr/volunteer/{app_b_id}")
    assert vol_qr_img.status_code == 200
    assert vol_qr_img.mimetype == "image/png"

    # Coordinator scans QR codes for Student A (participant) and Student B (volunteer)
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "respcoord@college.edu", "password": "SecurePass123!"},
    )
    scan_a = client.get(f"/attendance/validate/{reg_a_token}")
    scan_b = client.get(f"/attendance/validate/{app_b_token}")
    assert scan_a.status_code == 200
    assert scan_b.status_code == 200
    assert b"Attendance recorded successfully" in scan_a.data
    assert b"Attendance recorded successfully" in scan_b.data

    with app.app_context():
        att_b = Attendance.query.filter_by(event_id=event_id, student_id=student_b_id).one()
        assert att_b.method == "qr"
        assert att_b.registration_id is None
        assert att_b.volunteer_application_id == app_b_id

    # Student A & B see their respective certificates automatically in history and dashboard
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "part_qr@college.edu", "password": "SecurePass123!"},
    )
    hist_a = client.get("/certificates/history")
    assert hist_a.status_code == 200

    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "vol_qr@college.edu", "password": "SecurePass123!"},
    )
    dash_b = client.get("/student/")
    assert dash_b.status_code == 200

    with app.app_context():
        certs_a = Certificate.query.filter_by(recipient_id=student_a_id, event_id=event_id).all()
        certs_b = Certificate.query.filter_by(recipient_id=student_b_id, event_id=event_id).all()
        certs_c = Certificate.query.filter_by(recipient_id=student_c_id, event_id=event_id).all()
        certs_d = Certificate.query.filter_by(recipient_id=student_d_id, event_id=event_id).all()

        assert len(certs_a) == 1
        assert certs_a[0].certificate_type == "participation"
        assert certs_a[0].certificate_id.startswith("CPC-")

        assert len(certs_b) == 1
        assert certs_b[0].certificate_type == "volunteer"
        assert certs_b[0].certificate_id.startswith("CVC-")

        assert len(certs_c) == 0
        assert len(certs_d) == 0


def test_complete_event_issues_respective_certificates_and_upgrades_manual_on_qr_scan(client, app):
    coordinator_id = create_user(app, "coordinator", "compcoord@college.edu")
    student_id = create_user(app, "student", "compstudent@college.edu")
    event_id = create_event(app, coordinator_id, ended=False)

    with app.app_context():
        reg = EventRegistration(event_id=event_id, student_id=student_id, status="confirmed")
        db.session.add(reg)
        db.session.commit()
        qr_token = reg.qr_token

    login_as(client, coordinator_id)
    # Record manual attendance first
    client.post(f"/attendance/event/{event_id}", data={"student_id": student_id}, follow_redirects=True)
    with app.app_context():
        att = Attendance.query.filter_by(event_id=event_id, student_id=student_id).one()
        assert att.method == "manual"

    # Scanning QR code upgrades manual attendance to QR
    scan = client.get(f"/attendance/validate/{qr_token}")
    assert scan.status_code == 200
    assert b"Attendance recorded successfully" in scan.data
    with app.app_context():
        att = Attendance.query.filter_by(event_id=event_id, student_id=student_id).one()
        assert att.method == "qr"
        # Still active, so no certificate yet
        assert Certificate.query.filter_by(event_id=event_id).count() == 0

    # End the event explicitly -> auto-issues participation certificate
    complete_resp = client.post(f"/events/{event_id}/complete", follow_redirects=True)
    assert complete_resp.status_code == 200
    assert b"Event marked as ended" in complete_resp.data
    with app.app_context():
        event = db.session.get(Event, event_id)
        assert event.status == "completed"
        cert = Certificate.query.filter_by(event_id=event_id, recipient_id=student_id).one()
        assert cert.certificate_type == "participation"


def test_coordinator_qr_scan_endpoint_for_participant_volunteer_and_wrong_event(client, app):
    coordinator_id = create_user(app, "coordinator", "scancoord@college.edu")
    part_student_id = create_user(app, "student", "scanpart@college.edu")
    vol_student_id = create_user(app, "student", "scanvol@college.edu")
    event_id = create_event(app, coordinator_id, capacity=5, ended=False)

    with app.app_context():
        other_event = Event(
            title="Other Campus Event",
            slug="other-campus-event",
            description="Another campus event for mismatch testing.",
            category=EventCategory.query.first(),
            coordinator_id=coordinator_id,
            department=Department.query.first(),
            venue="Seminar Hall 1",
            organizer="CSE",
            event_date=date.today() + timedelta(days=5),
            start_time=time(10, 0),
            end_time=time(12, 0),
            registration_deadline=datetime.now() + timedelta(days=2),
            capacity=10,
            volunteer_requirement=2,
            status="published",
        )
        db.session.add(other_event)
        db.session.flush()
        reg = EventRegistration(event_id=event_id, student_id=part_student_id, status="confirmed")
        vol_app = VolunteerApplication(
            event_id=event_id,
            student_id=vol_student_id,
            preferred_role="Registration Desk",
            status="approved",
        )
        other_reg = EventRegistration(
            event_id=other_event.id,
            student_id=part_student_id,
            status="confirmed",
        )
        db.session.add_all([reg, vol_app, other_reg])
        db.session.commit()
        part_token = reg.qr_token
        vol_token = vol_app.qr_token
        other_token = other_reg.qr_token
        other_event_id = other_event.id

    login_as(client, coordinator_id)
    manage_page = client.get(f"/attendance/event/{event_id}")
    assert manage_page.status_code == 200
    assert b'id="qr-reader"' in manage_page.data
    assert b'id="start-qr-scanner"' in manage_page.data
    assert b'id="qr-image-input"' in manage_page.data
    assert b"html5-qrcode" in manage_page.data

    # Scan participant full QR URL
    part_scan = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": f"http://localhost/attendance/validate/{part_token}"},
    )
    assert part_scan.status_code == 200
    part_json = part_scan.get_json()
    assert part_json["valid"] is True
    assert part_json["duplicate"] is False
    assert part_json["roles"] == ["Participant"]

    # Repeat scan returns duplicate=True
    dup_scan = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": part_token},
    )
    assert dup_scan.status_code == 200
    assert dup_scan.get_json()["duplicate"] is True

    # Scan volunteer QR token
    vol_scan = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": vol_token},
    )
    assert vol_scan.status_code == 200
    vol_json = vol_scan.get_json()
    assert vol_json["valid"] is True
    assert vol_json["duplicate"] is False
    assert vol_json["roles"] == ["Volunteer"]

    # Invalid token
    bad_scan = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": "not-a-valid-token"},
    )
    assert bad_scan.status_code == 200
    assert bad_scan.get_json()["valid"] is False

    # Wrong event token
    wrong_scan = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": other_token},
    )
    assert wrong_scan.status_code == 200
    wrong_json = wrong_scan.get_json()
    assert wrong_json["valid"] is False
    assert "not this event" in wrong_json["message"]
    with app.app_context():
        assert Attendance.query.filter_by(event_id=other_event_id).count() == 0


def test_student_qr_and_unique_key_display_and_coordinator_key_checkin(client, app):
    coordinator_id = create_user(app, "coordinator", "keycoord@college.edu")
    part_student_id = create_user(app, "student", "keypart@college.edu")
    vol_student_id = create_user(app, "student", "keyvol@college.edu")
    event_id = create_event(app, coordinator_id, capacity=5, ended=False)

    with app.app_context():
        reg = EventRegistration(event_id=event_id, student_id=part_student_id, status="confirmed")
        vol_app = VolunteerApplication(
            event_id=event_id,
            student_id=vol_student_id,
            preferred_role="Registration Desk",
            status="approved",
        )
        db.session.add_all([reg, vol_app])
        db.session.commit()
        reg_id = reg.id
        app_id = vol_app.id
        part_key = reg.attendance_key
        vol_key = vol_app.attendance_key

    assert part_key.startswith(f"P-{reg_id}-")
    assert vol_key.startswith(f"V-{app_id}-")

    # Participant sees QR image & unique key on dashboard, registrations, and event detail
    login_as(client, part_student_id)
    for path in ("/student/", "/student/registrations", f"/events/{event_id}"):
        page = client.get(path)
        assert page.status_code == 200
        assert f"/attendance/qr/{reg_id}".encode() in page.data
        assert part_key.encode() in page.data

    # Approved volunteer sees volunteer QR image & unique key on dashboard, volunteering, and event detail
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "keyvol@college.edu", "password": "SecurePass123!"},
    )
    for path in ("/student/", "/student/volunteer-applications", f"/events/{event_id}"):
        page = client.get(path)
        assert page.status_code == 200
        assert f"/attendance/qr/volunteer/{app_id}".encode() in page.data
        assert vol_key.encode() in page.data

    # Coordinator enters unique keys when scanner does not work
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "keycoord@college.edu", "password": "SecurePass123!"},
    )

    # Lowercase participant key works via JSON scan endpoint
    part_res = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": part_key.lower()},
    )
    assert part_res.status_code == 200
    part_json = part_res.get_json()
    assert part_json["valid"] is True
    assert part_json["duplicate"] is False
    assert part_json["roles"] == ["Participant"]

    # Volunteer key works via non-JS POST fallback on /attendance/event/<id>
    vol_res = client.post(
        f"/attendance/event/{event_id}",
        data={"qr_token": vol_key},
        follow_redirects=True,
    )
    assert vol_res.status_code == 200
    assert b"Attendance recorded successfully" in vol_res.data

    # Forged key with wrong checksum is rejected
    forged_res = client.post(
        f"/attendance/event/{event_id}/scan",
        json={"qr_token": f"P-{reg_id}-000000"},
    )
    assert forged_res.status_code == 200
    assert forged_res.get_json()["valid"] is False

    with app.app_context():
        part_att = Attendance.query.filter_by(event_id=event_id, student_id=part_student_id).one()
        vol_att = Attendance.query.filter_by(event_id=event_id, student_id=vol_student_id).one()
        assert part_att.method == "qr"
        assert vol_att.method == "qr"
        assert vol_att.registration_id is None
        assert vol_att.volunteer_application_id == app_id


def test_compulsory_registration_event_workflow(client, app):
    admin_id = create_user(app, "admin", "compadmin@college.edu")
    student_id = create_user(app, "student", "compulsory_stu@college.edu")
    with app.app_context():
        category_id = EventCategory.query.first().id
        department_id = Department.query.first().id

    login_as(client, admin_id)
    create_resp = client.post(
        "/events/create",
        data={
            "title": "Mandatory Orientation",
            "description": "Mandatory campus orientation session for all department students.",
            "category_id": str(category_id),
            "department_id": str(department_id),
            "club_id": "0",
            "venue": "Main Auditorium",
            "organizer": "Computer Science Department",
            "event_date": (date.today() + timedelta(days=10)).isoformat(),
            "start_time": "09:00",
            "end_time": "12:00",
            "registration_deadline": (datetime.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            "volunteer_requirement": "0",
            "registration_compulsory": "y",
        },
        follow_redirects=True,
    )
    assert create_resp.status_code == 200

    with app.app_context():
        comp_event = Event.query.filter_by(title="Mandatory Orientation").one()
        assert comp_event.registration_compulsory is True
        comp_event_id = comp_event.id
        assert Notification.query.filter_by(
            user_id=student_id,
            title="Compulsory event: Mandatory Orientation",
        ).count() == 1

    # Admin sees unregistered student under pending compulsory registrations
    participants_before = client.get(f"/events/{comp_event_id}/participants")
    assert participants_before.status_code == 200
    assert b"Pending compulsory registrations" in participants_before.data
    assert b"STU-compulsory_stu" in participants_before.data

    # Student sees pending compulsory prompt on dashboard and badges on browse/detail
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "compulsory_stu@college.edu", "password": "SecurePass123!"},
    )
    dash_before = client.get("/student/")
    assert dash_before.status_code == 200
    assert b"Compulsory registrations required" in dash_before.data
    assert b"Mandatory Orientation" in dash_before.data

    browse_page = client.get("/events/")
    assert browse_page.status_code == 200
    assert b"Compulsory" in browse_page.data

    # Student registers -> removed from pending compulsory list & cannot cancel
    reg_resp = client.post(f"/events/{comp_event_id}/register", follow_redirects=True)
    assert reg_resp.status_code == 200
    assert b"Registration is compulsory and cannot be cancelled" in reg_resp.data
    assert b"Cancel registration" not in reg_resp.data

    dash_after = client.get("/student/")
    assert dash_after.status_code == 200
    assert b"Compulsory registrations required" not in dash_after.data

    cancel_attempt = client.post(
        f"/events/{comp_event_id}/registration/cancel",
        follow_redirects=True,
    )
    assert cancel_attempt.status_code == 200
    assert b"compulsory and cannot be cancelled" in cancel_attempt.data
    with app.app_context():
        assert EventRegistration.query.filter_by(
            event_id=comp_event_id,
            student_id=student_id,
        ).count() == 1

    # Non-compulsory event still allows cancellation
    normal_event_id = create_event(app, admin_id, capacity=5)
    client.post(f"/events/{normal_event_id}/register", follow_redirects=True)
    normal_cancel = client.post(
        f"/events/{normal_event_id}/registration/cancel",
        follow_redirects=True,
    )
    assert normal_cancel.status_code == 200
    assert b"registration has been cancelled" in normal_cancel.data
    with app.app_context():
        assert EventRegistration.query.filter_by(
            event_id=normal_event_id,
            student_id=student_id,
        ).count() == 0

    # Admin sees all eligible students registered on participants page
    client.get("/auth/logout")
    client.post(
        "/auth/login",
        data={"email": "compadmin@college.edu", "password": "SecurePass123!"},
    )
    participants_after = client.get(f"/events/{comp_event_id}/participants")
    assert participants_after.status_code == 200
    assert b"All eligible students have registered" in participants_after.data





