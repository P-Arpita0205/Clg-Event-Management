import os

from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

from app.firebase_config import init_firebase
from app.firestore_db import check_connection
from config import Config


csrf = CSRFProtect()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message_category = "warning"


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config.get("ENV") == "production" or os.environ.get("APP_ENV") == "production":
        if app.config["SECRET_KEY"].startswith("development-only"):
            raise RuntimeError("SECRET_KEY must be configured in production.")
        if app.config.get("FIRESTORE_BACKEND") != "memory":
            if not app.config.get("FIREBASE_PROJECT_ID"):
                raise RuntimeError("FIREBASE_PROJECT_ID must be configured in production.")
            if not (
                app.config.get("FIREBASE_CREDENTIALS_PATH")
                or app.config.get("FIREBASE_CREDENTIALS_JSON")
            ):
                raise RuntimeError(
                    "FIREBASE_CREDENTIALS_PATH or FIREBASE_CREDENTIALS_JSON must be configured in production."
                )

    init_firebase(app)
    csrf.init_app(app)
    login_manager.init_app(app)

    @app.after_request
    def add_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if app.config.get("SESSION_COOKIE_SECURE"):
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response

    @app.errorhandler(403)
    def forbidden(error):
        return app.jinja_env.get_template("errors/403.html").render(), 403

    @app.errorhandler(404)
    def not_found(error):
        return app.jinja_env.get_template("errors/404.html").render(), 404

    @app.errorhandler(413)
    def file_too_large(error):
        from flask import flash, redirect, request

        flash("The uploaded file is too large.", "danger")
        return redirect(request.referrer or "/"), 413

    @app.errorhandler(500)
    def server_error(error):
        app.logger.exception("Unhandled server error")
        return app.jinja_env.get_template("errors/500.html").render(), 500

    @app.route("/health")
    def health():
        check_connection()
        return {"status": "ok", "database": "firestore"}, 200

    from app.auth import auth
    from app.main import main
    from app.admin import admin
    from app.coordinator import coordinator
    from app.student import student
    from app.events import events
    from app.attendance import attendance
    from app.tasks import tasks
    from app.notifications import notifications
    from app.certificates import certificates
    from app.analytics import analytics
    from app.feedback import feedback
    from app.community import community
    from app.advanced import advanced
    from app.assistance import assistance

    app.register_blueprint(main)
    app.register_blueprint(auth)
    app.register_blueprint(admin)
    app.register_blueprint(coordinator)
    app.register_blueprint(student)
    app.register_blueprint(events)
    app.register_blueprint(attendance)
    app.register_blueprint(tasks)
    app.register_blueprint(notifications)
    app.register_blueprint(certificates)
    app.register_blueprint(analytics)
    app.register_blueprint(feedback)
    app.register_blueprint(community)
    app.register_blueprint(advanced)
    app.register_blueprint(assistance)

    from app import models  # noqa: F401

    @app.context_processor
    def notification_context():
        from flask_login import current_user
        from app.models import Notification

        if current_user.is_authenticated:
            unread = Notification.count(user_id=current_user.id, is_read=False)
            return {"unread_notification_count": unread}
        return {"unread_notification_count": 0}

    @app.cli.command("init-db")
    def init_db():
        """Seed roles, departments, event categories, and default resources in Firestore."""
        from app.models import Department, EventCategory, Resource, Role

        for name in ("admin", "coordinator", "student"):
            if not Role.find_one(name=name):
                Role(name=name).save()

        departments = (
            ("Computer Science", "CSE"),
            ("Information Technology", "IT"),
            ("Electronics", "ECE"),
            ("Mechanical Engineering", "ME"),
            ("Civil Engineering", "CE"),
            ("Management", "MBA"),
        )
        for name, code in departments:
            if not Department.find_one(code=code):
                Department(name=name, code=code).save()

        for name in ("Technical", "Cultural", "Sports", "Workshop", "Seminar", "Fest"):
            if not EventCategory.find_one(name=name):
                EventCategory(name=name).save()

        default_resources = [
            ("Main Auditorium", "Auditorium", "Block A, Ground Floor", 500),
            ("Seminar Hall 1", "Seminar Hall", "Block B, 1st Floor", 120),
            ("Seminar Hall 2", "Seminar Hall", "Block B, 2nd Floor", 120),
            ("Computer Lab 1", "Laboratory", "Block C, Ground Floor", 60),
            ("Computer Lab 2", "Laboratory", "Block C, 1st Floor", 60),
            ("Conference Room", "Classroom", "Admin Block, 2nd Floor", 30),
            ("Sports Ground", "Sports Facility", "Campus Ground", 1000),
            ("Library Hall", "Seminar Hall", "Library Block, 1st Floor", 80),
        ]
        for res_name, res_type, location, capacity in default_resources:
            if not Resource.find_one(name=res_name):
                Resource(
                    name=res_name,
                    resource_type=res_type,
                    location=location,
                    capacity=capacity,
                    is_active=True,
                ).save()

        print("Firestore collections initialized.")

    @app.cli.command("create-admin")
    def create_admin():
        """Securely create or update an administrator account in Firestore."""
        import getpass
        from app.models import Department, Role, User

        role = Role.find_one(name="admin")
        if not role:
            role = Role(name="admin").save()

        email = input("Administrator email: ").strip().lower()
        full_name = input("Administrator full name: ").strip()
        password = getpass.getpass("Temporary password: ")
        confirm = getpass.getpass("Confirm password: ")
        if not email or not full_name:
            raise RuntimeError("Email and full name are required.")
        if len(password) < 12:
            raise RuntimeError("Password must contain at least 12 characters.")
        if password != confirm:
            raise RuntimeError("Passwords do not match.")

        user = User.find_one(email=email)
        if user:
            if user.role_id != role.id:
                raise RuntimeError("The email belongs to a non-admin account.")
            user.full_name = full_name
            user.is_active = True
        else:
            departments = Department.all()
            user = User(
                full_name=full_name,
                email=email,
                student_id="ADMIN-" + email.split("@")[0],
                role=role,
                department=departments[0] if departments else None,
            )
        user.set_password(password)
        user.save()
        print("Administrator account created in Firestore. Change the password after first login.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Create idempotent demo accounts and data in Firestore for local testing."""
        from datetime import date, datetime, time, timedelta
        from app.models import (
            Department,
            Event,
            EventCategory,
            EventRegistration,
            Resource,
            Role,
            User,
            VolunteerApplication,
            VolunteerAssignment,
            VolunteerTask,
        )

        departments = Department.all()
        department = departments[0] if departments else Department(name="Computer Science", code="CSE").save()

        for name in ("Technical", "Cultural", "Sports", "Workshop", "Seminar", "Fest"):
            if not EventCategory.find_one(name=name):
                EventCategory(name=name).save()

        for name in ("admin", "coordinator", "student"):
            if not Role.find_one(name=name):
                Role(name=name).save()

        demo_accounts = (
            ("admin@college.edu", "Demo Admin", "admin", "ADM001"),
            ("coordinator@college.edu", "Demo Coordinator", "coordinator", "COORD001"),
            ("student@college.edu", "Demo Student", "student", "STU001"),
        )
        for email, name, role_name, student_id in demo_accounts:
            if not User.find_one(email=email):
                user = User(
                    full_name=name,
                    email=email,
                    student_id=student_id,
                    role=Role.find_one(name=role_name),
                    department=department,
                )
                user.set_password("CampusDemo123!")
                user.save()

        coordinator = User.find_one(email="coordinator@college.edu")
        category = EventCategory.find_one(name="Technical")
        if coordinator and category and not Event.find_one(title="Campus Innovation Expo"):
            Event(
                title="Campus Innovation Expo",
                slug="campus-innovation-expo",
                description="A campus showcase of student projects, prototypes, and technical innovations.",
                category=category,
                coordinator=coordinator,
                department=department,
                venue="Main Auditorium",
                organizer="Computer Science Department",
                event_date=date.today() + timedelta(days=14),
                start_time=time(10, 0),
                end_time=time(15, 0),
                registration_deadline=datetime.now() + timedelta(days=10),
                capacity=200,
                volunteer_requirement=12,
                status="published",
            ).save()

        default_resources = [
            ("Main Auditorium", "Auditorium", "Block A, Ground Floor", 500),
            ("Seminar Hall 1", "Seminar Hall", "Block B, 1st Floor", 120),
            ("Seminar Hall 2", "Seminar Hall", "Block B, 2nd Floor", 120),
            ("Computer Lab 1", "Laboratory", "Block C, Ground Floor", 60),
            ("Computer Lab 2", "Laboratory", "Block C, 1st Floor", 60),
            ("Conference Room", "Classroom", "Admin Block, 2nd Floor", 30),
            ("Sports Ground", "Sports Facility", "Campus Ground", 1000),
            ("Library Hall", "Seminar Hall", "Library Block, 1st Floor", 80),
        ]
        for res_name, res_type, location, capacity in default_resources:
            if not Resource.find_one(name=res_name):
                Resource(
                    name=res_name,
                    resource_type=res_type,
                    location=location,
                    capacity=capacity,
                    is_active=True,
                ).save()

        student_user = User.find_one(email="student@college.edu")
        expo_event = Event.find_one(title="Campus Innovation Expo")
        if student_user and expo_event:
            if not EventRegistration.find_one(event_id=expo_event.id, student_id=student_user.id):
                EventRegistration(
                    event_id=expo_event.id,
                    student_id=student_user.id,
                    status="confirmed",
                ).save()

            app_rec = VolunteerApplication.find_one(event_id=expo_event.id, student_id=student_user.id)
            if not app_rec:
                app_rec = VolunteerApplication(
                    event_id=expo_event.id,
                    student_id=student_user.id,
                    preferred_role="Registration Desk",
                    availability="Flexible",
                    experience="Helped organize high school tech fair and department orientation.",
                    status="approved",
                ).save()

            assignment = VolunteerAssignment.find_one(application_id=app_rec.id)
            if not assignment:
                assignment = VolunteerAssignment(
                    application_id=app_rec.id,
                    volunteer_role="Registration Desk Lead",
                    responsibilities="Coordinate desk check-in and attendee kits",
                ).save()

            if not VolunteerTask.find_one(assignment_id=assignment.id):
                VolunteerTask(
                    event_id=expo_event.id,
                    assignment_id=assignment.id,
                    title="Prepare attendee kits and badges",
                    description="Assemble welcome badges, ID lanyards, and event schedules for incoming participants.",
                    deadline=datetime.now() + timedelta(days=5),
                    status="assigned",
                ).save()
                VolunteerTask(
                    event_id=expo_event.id,
                    assignment_id=assignment.id,
                    title="Setup registration desk and QR scanners",
                    description="Check desk connectivity, test scanner stations, and verify attendee check-in software.",
                    deadline=datetime.now() + timedelta(days=12),
                    status="in_progress",
                ).save()

        print("Demo data initialized in Firestore.")

    return app
