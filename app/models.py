import hashlib
import secrets
from datetime import datetime, time, timezone

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import db, login_manager


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(30), unique=True, nullable=False)

    users = db.relationship("User", back_populates="role")


class Department(db.Model):
    __tablename__ = "departments"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    code = db.Column(db.String(20), unique=True, nullable=False)

    users = db.relationship("User", back_populates="department")


class Club(db.Model):
    __tablename__ = "clubs"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    description = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True, nullable=False)


class EventCategory(db.Model):
    __tablename__ = "event_categories"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    events = db.relationship("Event", back_populates="category")


class Event(db.Model):
    __tablename__ = "events"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    poster = db.Column(db.String(255))
    category_id = db.Column(db.Integer, db.ForeignKey("event_categories.id"), nullable=False, index=True)
    coordinator_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"), index=True)
    club_id = db.Column(db.Integer, db.ForeignKey("clubs.id"))
    venue = db.Column(db.String(160), nullable=False)
    organizer = db.Column(db.String(160), nullable=False)
    event_date = db.Column(db.Date, nullable=False, index=True)
    end_date = db.Column(db.Date, nullable=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    registration_deadline = db.Column(db.DateTime, nullable=False)
    capacity = db.Column(db.Integer, nullable=False)
    volunteer_requirement = db.Column(db.Integer, nullable=False, default=0)
    registration_compulsory = db.Column(db.Boolean, nullable=False, default=False)
    status = db.Column(db.String(20), nullable=False, default="draft", index=True)
    approval_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    category = db.relationship("EventCategory", back_populates="events")
    coordinator = db.relationship("User", foreign_keys=[coordinator_id])
    department = db.relationship("Department")
    club = db.relationship("Club")
    registrations = db.relationship(
        "EventRegistration", back_populates="event", cascade="all, delete-orphan"
    )
    volunteer_applications = db.relationship(
        "VolunteerApplication", back_populates="event", cascade="all, delete-orphan"
    )

    @property
    def approved_registration_count(self):
        return sum(1 for registration in self.registrations if registration.status == "confirmed")

    @property
    def approved_volunteer_count(self):
        return sum(1 for application in self.volunteer_applications if application.status == "approved")

    @property
    def volunteer_limit_reached(self):
        return self.volunteer_requirement > 0 and self.approved_volunteer_count >= self.volunteer_requirement

    @property
    def end_datetime(self):
        """Return the effective local end datetime of the event."""
        effective_end_date = self.end_date or self.event_date
        if self.end_time and (
            self.end_time != self.start_time
            or (self.end_date and self.end_date > self.event_date)
        ):
            effective_end_time = self.end_time
        else:
            effective_end_time = time(23, 59, 59)
        return datetime.combine(effective_end_date, effective_end_time)

    @property
    def has_ended(self):
        """Return True once the event is completed or past its scheduled end."""
        if self.status == "completed":
            return True
        if self.status != "published":
            return False
        return datetime.now() >= self.end_datetime


def _make_attendance_key(prefix, record_id, qr_token):
    """Build a short verifiable attendance key from a record ID and QR token."""
    if not record_id or not qr_token:
        return None
    digest = hashlib.sha256(qr_token.encode("utf-8")).hexdigest()[:6].upper()
    return f"{prefix}-{record_id}-{digest}"


class EventRegistration(db.Model):
    __tablename__ = "event_registrations"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmed")
    qr_token = db.Column(db.String(64), unique=True, nullable=False, default=lambda: secrets.token_urlsafe(32))
    registered_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    event = db.relationship("Event", back_populates="registrations")
    student = db.relationship("User")

    @property
    def attendance_key(self):
        return _make_attendance_key("P", self.id, self.qr_token)

    __table_args__ = (
        db.UniqueConstraint("event_id", "student_id", name="uq_event_student_registration"),
        db.Index("ix_event_registration_status", "event_id", "status"),
    )


class VolunteerApplication(db.Model):
    __tablename__ = "volunteer_applications"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    availability = db.Column(db.String(255), nullable=True, default="Flexible")
    experience = db.Column(db.Text)
    preferred_role = db.Column(db.String(100))
    status = db.Column(db.String(20), nullable=False, default="pending", index=True)
    qr_token = db.Column(db.String(64), unique=True, nullable=True, default=lambda: secrets.token_urlsafe(32))
    reviewed_at = db.Column(db.DateTime)
    reviewer_note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    event = db.relationship("Event", back_populates="volunteer_applications")
    student = db.relationship("User")
    assignment = db.relationship(
        "VolunteerAssignment", back_populates="application", uselist=False
    )

    @property
    def attendance_key(self):
        return _make_attendance_key("V", self.id, self.qr_token)

    __table_args__ = (
        db.UniqueConstraint("event_id", "student_id", name="uq_event_student_application"),
        db.Index("ix_volunteer_application_status", "event_id", "status"),
    )


class VolunteerAssignment(db.Model):
    __tablename__ = "volunteer_assignments"

    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey("volunteer_applications.id"), unique=True, nullable=False)
    volunteer_role = db.Column(db.String(100), nullable=False)
    responsibilities = db.Column(db.Text)
    assigned_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    application = db.relationship("VolunteerApplication", back_populates="assignment")


class VolunteerTask(db.Model):
    __tablename__ = "volunteer_tasks"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    assignment_id = db.Column(db.Integer, db.ForeignKey("volunteer_assignments.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text)
    deadline = db.Column(db.DateTime)
    status = db.Column(db.String(20), nullable=False, default="assigned", index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    event = db.relationship("Event")
    assignment = db.relationship("VolunteerAssignment")


class Attendance(db.Model):
    __tablename__ = "attendance"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    registration_id = db.Column(db.Integer, db.ForeignKey("event_registrations.id"), nullable=True)
    volunteer_application_id = db.Column(db.Integer, db.ForeignKey("volunteer_applications.id"), nullable=True)
    checked_in_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    method = db.Column(db.String(20), nullable=False, default="qr")

    event = db.relationship("Event")
    student = db.relationship("User")
    registration = db.relationship("EventRegistration")
    volunteer_application = db.relationship("VolunteerApplication")

    __table_args__ = (
        db.UniqueConstraint("event_id", "student_id", name="uq_event_student_attendance"),
        db.Index("ix_attendance_event", "event_id"),
    )


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    message = db.Column(db.String(500), nullable=False)
    link = db.Column(db.String(255))
    is_read = db.Column(db.Boolean, default=False, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    user = db.relationship("User")


class Certificate(db.Model):
    __tablename__ = "certificates"

    id = db.Column(db.Integer, primary_key=True)
    certificate_id = db.Column(db.String(40), unique=True, nullable=False, index=True)
    recipient_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    certificate_type = db.Column(db.String(30), nullable=False, index=True)
    issue_date = db.Column(db.Date, nullable=False, default=lambda: datetime.now(timezone.utc).date())
    pdf_path = db.Column(db.String(255))
    is_valid = db.Column(db.Boolean, default=True, nullable=False)
    issued_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    recipient = db.relationship("User", foreign_keys=[recipient_id])
    issuer = db.relationship("User", foreign_keys=[issued_by])
    event = db.relationship("Event")

    __table_args__ = (
        db.UniqueConstraint(
            "recipient_id",
            "event_id",
            "certificate_type",
            name="uq_certificate_recipient_event_type",
        ),
    )


class Feedback(db.Model):
    __tablename__ = "feedback"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    rating = db.Column(db.Integer, nullable=False)
    suggestions = db.Column(db.Text)
    is_anonymous = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    event = db.relationship("Event")
    student = db.relationship("User")

    __table_args__ = (
        db.UniqueConstraint("event_id", "student_id", name="uq_feedback_event_student"),
        db.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_feedback_rating"),
    )


class EventGallery(db.Model):
    __tablename__ = "event_galleries"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    caption = db.Column(db.String(255))
    uploaded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    event = db.relationship("Event")
    uploader = db.relationship("User", foreign_keys=[uploaded_by])


class VolunteerHours(db.Model):
    __tablename__ = "volunteer_hours"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=False)
    hours = db.Column(db.Numeric(6, 2), nullable=False)
    note = db.Column(db.String(255))
    recorded_by = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    recorded_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    student = db.relationship("User", foreign_keys=[student_id])
    event = db.relationship("Event")
    recorder = db.relationship("User", foreign_keys=[recorded_by])

    __table_args__ = (
        db.CheckConstraint("hours >= 0", name="ck_volunteer_hours_positive"),
    )


class EventBudget(db.Model):
    __tablename__ = "event_budgets"

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), unique=True, nullable=False)
    allocated_amount = db.Column(db.Numeric(12, 2), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    event = db.relationship("Event")
    expenses = db.relationship("EventExpense", back_populates="budget", cascade="all, delete-orphan")


class EventExpense(db.Model):
    __tablename__ = "event_expenses"

    id = db.Column(db.Integer, primary_key=True)
    budget_id = db.Column(db.Integer, db.ForeignKey("event_budgets.id"), nullable=False)
    category = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    expense_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    budget = db.relationship("EventBudget", back_populates="expenses")


class Resource(db.Model):
    __tablename__ = "resources"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), unique=True, nullable=False)
    resource_type = db.Column(db.String(50), nullable=False)
    location = db.Column(db.String(160))
    capacity = db.Column(db.Integer)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    bookings = db.relationship("ResourceBooking", back_populates="resource", cascade="all, delete-orphan")


class ResourceBooking(db.Model):
    __tablename__ = "resource_bookings"

    id = db.Column(db.Integer, primary_key=True)
    resource_id = db.Column(db.Integer, db.ForeignKey("resources.id"), nullable=False)
    event_id = db.Column(db.Integer, db.ForeignKey("events.id"), nullable=True)
    requester_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    purpose = db.Column(db.String(255), nullable=False)
    booking_date = db.Column(db.Date, nullable=False, index=True)
    start_time = db.Column(db.Time, nullable=False)
    end_time = db.Column(db.Time, nullable=False)
    status = db.Column(db.String(20), nullable=False, default="confirmed", index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    resource = db.relationship("Resource", back_populates="bookings")
    event = db.relationship("Event")
    requester = db.relationship("User")


class StudentInterest(db.Model):
    __tablename__ = "student_interests"

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("event_categories.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)

    student = db.relationship("User")
    category = db.relationship("EventCategory")

    __table_args__ = (
        db.UniqueConstraint("student_id", "category_id", name="uq_student_category_interest"),
    )


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(180), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    student_id = db.Column(db.String(50), unique=True)
    phone = db.Column(db.String(20))
    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    department_id = db.Column(db.Integer, db.ForeignKey("departments.id"))
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), nullable=False)
    updated_at = db.Column(
        db.DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    role = db.relationship("Role", back_populates="users")
    department = db.relationship("Department", back_populates="users")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self):
        return self.role.name if self.role else None


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))
