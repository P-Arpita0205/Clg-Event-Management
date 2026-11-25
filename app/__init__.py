import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

from config import Config


db = SQLAlchemy()
migrate = Migrate()
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
        if not os.environ.get("DATABASE_URL", "").startswith(("mysql://", "mysql+pymysql://", "sqlite:///")):
            raise RuntimeError("A valid DATABASE_URL (mysql or sqlite) must be configured in production.")

    db.init_app(app)
    migrate.init_app(app, db)
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
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        return app.jinja_env.get_template("errors/500.html").render(), 500

    @app.route("/health")
    def health():
        from sqlalchemy import text
        db.session.execute(text("SELECT 1"))
        return {"status": "ok", "database": "connected"}, 200

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
            unread = Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False,
            ).count()
            return {"unread_notification_count": unread}
        return {"unread_notification_count": 0}

    @app.cli.command("init-db")
    def init_db():
        """Create tables and seed roles and departments."""
        db.create_all()
        from app.models import Role, Department, EventCategory

        for name in ("admin", "coordinator", "student"):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name))

        departments = (
            ("Computer Science", "CSE"),
            ("Information Technology", "IT"),
            ("Electronics", "ECE"),
            ("Mechanical Engineering", "ME"),
            ("Civil Engineering", "CE"),
            ("Management", "MBA"),
        )
        for name, code in departments:
            if not Department.query.filter_by(code=code).first():
                db.session.add(Department(name=name, code=code))

        for name in (
            "Technical",
            "Cultural",
            "Sports",
            "Workshop",
            "Seminar",
            "Fest",
        ):
            if not EventCategory.query.filter_by(name=name).first():
                db.session.add(EventCategory(name=name))

        from app.models import Resource
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
            if not Resource.query.filter_by(name=res_name).first():
                db.session.add(Resource(
                    name=res_name,
                    resource_type=res_type,
                    location=location,
                    capacity=capacity,
                    is_active=True,
                ))

        db.session.commit()
        print("Database initialized.")

    @app.cli.command("create-admin")
    def create_admin():
        """Securely create or update the initial administrator account."""
        import getpass
        from app.models import Role, Department, User

        db.create_all()
        role = Role.query.filter_by(name="admin").first()
        if not role:
            role = Role(name="admin")
            db.session.add(role)
            db.session.flush()

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

        user = User.query.filter_by(email=email).first()
        if user:
            if user.role_id != role.id:
                raise RuntimeError("The email belongs to a non-admin account.")
            user.full_name = full_name
            user.is_active = True
        else:
            user = User(
                full_name=full_name,
                email=email,
                student_id="ADMIN-" + email.split("@")[0],
                role=role,
                department=Department.query.first(),
            )
            db.session.add(user)
        user.set_password(password)
        db.session.commit()
        print("Administrator account created. Change the password after first login.")

    @app.cli.command("seed-demo")
    def seed_demo():
        """Create idempotent demo accounts and data for local testing."""
        from datetime import date, time, timedelta, datetime
        from app.models import (
            Role,
            Department,
            EventCategory,
            User,
            Event,
            Resource,
            EventRegistration,
            VolunteerApplication,
            VolunteerAssignment,
            VolunteerTask,
        )

        db.create_all()
        department = Department.query.first()
        if not department:
            department = Department(name="Computer Science", code="CSE")
            db.session.add(department)
        for name in ("Technical", "Cultural", "Sports", "Workshop", "Seminar", "Fest"):
            if not EventCategory.query.filter_by(name=name).first():
                db.session.add(EventCategory(name=name))
        for name in ("admin", "coordinator", "student"):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name))
        db.session.flush()

        for name in ("admin", "coordinator", "student"):
            if not Role.query.filter_by(name=name).first():
                db.session.add(Role(name=name))
        db.session.flush()

        demo_accounts = (
            ("admin@college.edu", "Demo Admin", "admin", "ADM001"),
            ("coordinator@college.edu", "Demo Coordinator", "coordinator", "COORD001"),
            ("student@college.edu", "Demo Student", "student", "STU001"),
        )
        department = Department.query.first()
        for email, name, role_name, student_id in demo_accounts:
            user = User.query.filter_by(email=email).first()
            if not user:
                user = User(
                    full_name=name,
                    email=email,
                    student_id=student_id,
                    role=Role.query.filter_by(name=role_name).first(),
                    department=department,
                )
                user.set_password("CampusDemo123!")
                db.session.add(user)
        db.session.flush()

        coordinator = User.query.filter_by(email="coordinator@college.edu").first()
        category = EventCategory.query.filter_by(name="Technical").first()
        if coordinator and category and not Event.query.filter_by(title="Campus Innovation Expo").first():
            db.session.add(
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
                )
            )
        # Seed default campus resources
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
            if not Resource.query.filter_by(name=res_name).first():
                db.session.add(Resource(
                    name=res_name,
                    resource_type=res_type,
                    location=location,
                    capacity=capacity,
                    is_active=True,
                ))

        # Seed demo student engagement (registration, volunteer assignment, and assigned tasks)
        student_user = User.query.filter_by(email="student@college.edu").first()
        expo_event = Event.query.filter_by(title="Campus Innovation Expo").first()
        if student_user and expo_event:
            import uuid
            if not EventRegistration.query.filter_by(event_id=expo_event.id, student_id=student_user.id).first():
                db.session.add(
                    EventRegistration(
                        event_id=expo_event.id,
                        student_id=student_user.id,
                        status="confirmed",
                    )
                )
                db.session.flush()

            app_rec = VolunteerApplication.query.filter_by(event_id=expo_event.id, student_id=student_user.id).first()
            if not app_rec:
                app_rec = VolunteerApplication(
                    event_id=expo_event.id,
                    student_id=student_user.id,
                    preferred_role="Registration Desk",
                    availability="Flexible",
                    experience="Helped organize high school tech fair and department orientation.",
                    status="approved",
                )
                db.session.add(app_rec)
                db.session.flush()

            assignment = VolunteerAssignment.query.filter_by(application_id=app_rec.id).first()
            if not assignment:
                assignment = VolunteerAssignment(
                    application_id=app_rec.id,
                    volunteer_role="Registration Desk Lead",
                    responsibilities="Coordinate desk check-in and attendee kits",
                )
                db.session.add(assignment)
                db.session.flush()

            if not VolunteerTask.query.filter_by(assignment_id=assignment.id).first():
                db.session.add(
                    VolunteerTask(
                        event_id=expo_event.id,
                        assignment_id=assignment.id,
                        title="Prepare attendee kits and badges",
                        description="Assemble welcome badges, ID lanyards, and event schedules for incoming participants.",
                        deadline=datetime.now() + timedelta(days=5),
                        status="assigned",
                    )
                )
                db.session.add(
                    VolunteerTask(
                        event_id=expo_event.id,
                        assignment_id=assignment.id,
                        title="Setup registration desk and QR scanners",
                        description="Check desk connectivity, test scanner stations, and verify attendee check-in software.",
                        deadline=datetime.now() + timedelta(days=12),
                        status="in_progress",
                    )
                )

        db.session.commit()
        print("Demo data initialized.")

    return app
