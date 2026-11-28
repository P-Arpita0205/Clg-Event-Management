"""Domain models backed by Google Cloud Firestore collections."""

from datetime import datetime, time, timezone
from decimal import Decimal
import hashlib
import secrets

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from app import login_manager
from app.firestore_db import (
    batch_write,
    count_docs,
    create_doc,
    delete_doc,
    find_one,
    get_doc,
    list_docs,
    parse_date,
    parse_datetime,
    parse_decimal,
    parse_time,
    update_doc,
)


def _utcnow():
    return datetime.now(timezone.utc)


def _make_attendance_key(prefix, record_id, qr_token):
    """Build a short verifiable attendance key from a record ID and QR token."""
    if not record_id or not qr_token:
        return None
    digest = hashlib.sha256(qr_token.encode("utf-8")).hexdigest()[:6].upper()
    return f"{prefix}-{record_id}-{digest}"


class FirestoreModel:
    """Base active-record wrapper over a Cloud Firestore collection."""

    collection_name = ""
    _fields = ()

    def __init__(self, **kwargs):
        self.id = kwargs.get("id")

    @classmethod
    def get(cls, doc_id):
        if doc_id is None:
            return None
        try:
            lookup_id = int(doc_id)
        except (TypeError, ValueError):
            return None
        data = get_doc(cls.collection_name, lookup_id)
        return cls.from_dict(data) if data else None

    @classmethod
    def all(cls):
        return [cls.from_dict(data) for data in list_docs(cls.collection_name)]

    @classmethod
    def where(cls, **filters):
        return [cls.from_dict(data) for data in list_docs(cls.collection_name, filters=filters)]

    @classmethod
    def find_one(cls, **filters):
        data = find_one(cls.collection_name, **filters)
        return cls.from_dict(data) if data else None

    @classmethod
    def count(cls, **filters):
        return count_docs(cls.collection_name, **filters)

    @classmethod
    def from_dict(cls, data):
        return cls(**data)

    def to_dict(self):
        return {field: getattr(self, field) for field in self._fields}

    def save(self):
        payload = self.to_dict()
        if self.id is None:
            created = create_doc(self.collection_name, payload)
            self.id = created["id"]
        else:
            update_doc(self.collection_name, self.id, payload)
        return self

    def delete(self):
        if self.id is not None:
            delete_doc(self.collection_name, self.id)


class Role(FirestoreModel):
    collection_name = "roles"
    _fields = ("name",)

    def __init__(self, id=None, name="", **kwargs):
        super().__init__(id=id)
        self.name = name

    @property
    def users(self):
        return User.where(role_id=self.id) if self.id is not None else []


class Department(FirestoreModel):
    collection_name = "departments"
    _fields = ("name", "code")

    def __init__(self, id=None, name="", code="", **kwargs):
        super().__init__(id=id)
        self.name = name
        self.code = code

    @property
    def users(self):
        return User.where(department_id=self.id) if self.id is not None else []


class Club(FirestoreModel):
    collection_name = "clubs"
    _fields = ("name", "description", "is_active")

    def __init__(self, id=None, name="", description=None, is_active=True, **kwargs):
        super().__init__(id=id)
        self.name = name
        self.description = description
        self.is_active = bool(is_active)


class EventCategory(FirestoreModel):
    collection_name = "event_categories"
    _fields = ("name",)

    def __init__(self, id=None, name="", **kwargs):
        super().__init__(id=id)
        self.name = name

    @property
    def events(self):
        return Event.where(category_id=self.id) if self.id is not None else []


class Event(FirestoreModel):
    collection_name = "events"
    _fields = (
        "title",
        "slug",
        "description",
        "poster",
        "category_id",
        "coordinator_id",
        "department_id",
        "club_id",
        "venue",
        "organizer",
        "event_date",
        "end_date",
        "start_time",
        "end_time",
        "registration_deadline",
        "capacity",
        "volunteer_requirement",
        "registration_compulsory",
        "status",
        "approval_note",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        id=None,
        title="",
        slug="",
        description="",
        poster=None,
        category_id=None,
        category=None,
        coordinator_id=None,
        coordinator=None,
        department_id=None,
        department=None,
        club_id=None,
        club=None,
        venue="",
        organizer="",
        event_date=None,
        end_date=None,
        start_time=None,
        end_time=None,
        registration_deadline=None,
        capacity=100000,
        volunteer_requirement=0,
        registration_compulsory=False,
        status="draft",
        approval_note=None,
        created_at=None,
        updated_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.title = title
        self.slug = slug
        self.description = description
        self.poster = poster
        self.category_id = category.id if category is not None else category_id
        self.coordinator_id = coordinator.id if coordinator is not None else coordinator_id
        self.department_id = department.id if department is not None else department_id
        self.club_id = club.id if club is not None else club_id
        self.venue = venue
        self.organizer = organizer
        self.event_date = parse_date(event_date)
        self.end_date = parse_date(end_date)
        self.start_time = parse_time(start_time)
        self.end_time = parse_time(end_time)
        self.registration_deadline = parse_datetime(registration_deadline, naive=True)
        self.capacity = int(capacity) if capacity is not None else 100000
        self.volunteer_requirement = int(volunteer_requirement or 0)
        self.registration_compulsory = bool(registration_compulsory)
        self.status = status or "draft"
        self.approval_note = approval_note
        self.created_at = parse_datetime(created_at) or _utcnow()
        self.updated_at = parse_datetime(updated_at) or _utcnow()

    def save(self):
        self.updated_at = _utcnow()
        return super().save()

    @property
    def category(self):
        return EventCategory.get(self.category_id)

    @property
    def coordinator(self):
        return User.get(self.coordinator_id)

    @property
    def department(self):
        return Department.get(self.department_id)

    @property
    def club(self):
        return Club.get(self.club_id)

    @property
    def registrations(self):
        return EventRegistration.where(event_id=self.id) if self.id is not None else []

    @property
    def volunteer_applications(self):
        return VolunteerApplication.where(event_id=self.id) if self.id is not None else []

    @property
    def approved_registration_count(self):
        if self.id is None:
            return 0
        return EventRegistration.count(event_id=self.id, status="confirmed")

    @property
    def approved_volunteer_count(self):
        if self.id is None:
            return 0
        return VolunteerApplication.count(event_id=self.id, status="approved")

    @property
    def volunteer_limit_reached(self):
        return (
            self.volunteer_requirement > 0
            and self.approved_volunteer_count >= self.volunteer_requirement
        )

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

    def delete_with_related(self):
        """Delete the event and all dependent Firestore documents in batches."""
        if self.id is None:
            return
        ops = []
        apps = VolunteerApplication.where(event_id=self.id)
        for app_rec in apps:
            assignment = VolunteerAssignment.find_one(application_id=app_rec.id)
            if assignment:
                ops.append(("delete", VolunteerAssignment.collection_name, assignment.id))
            ops.append(("delete", VolunteerApplication.collection_name, app_rec.id))

        for budget in EventBudget.where(event_id=self.id):
            for expense in EventExpense.where(budget_id=budget.id):
                ops.append(("delete", EventExpense.collection_name, expense.id))
            ops.append(("delete", EventBudget.collection_name, budget.id))

        for model_cls in (
            EventRegistration,
            VolunteerTask,
            Attendance,
            Certificate,
            Feedback,
            EventGallery,
            VolunteerHours,
            ResourceBooking,
        ):
            for item in model_cls.where(event_id=self.id):
                ops.append(("delete", model_cls.collection_name, item.id))

        ops.append(("delete", self.collection_name, self.id))
        batch_write(ops)


class EventRegistration(FirestoreModel):
    collection_name = "event_registrations"
    _fields = ("event_id", "student_id", "status", "qr_token", "registered_at")

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        student_id=None,
        student=None,
        status="confirmed",
        qr_token=None,
        registered_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.student_id = student.id if student is not None else student_id
        self.status = status or "confirmed"
        self.qr_token = qr_token or secrets.token_urlsafe(32)
        self.registered_at = parse_datetime(registered_at) or _utcnow()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def attendance_key(self):
        return _make_attendance_key("P", self.id, self.qr_token)


class VolunteerApplication(FirestoreModel):
    collection_name = "volunteer_applications"
    _fields = (
        "event_id",
        "student_id",
        "availability",
        "experience",
        "preferred_role",
        "status",
        "qr_token",
        "reviewed_at",
        "reviewer_note",
        "created_at",
    )

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        student_id=None,
        student=None,
        availability="Flexible",
        experience=None,
        preferred_role=None,
        status="pending",
        qr_token=None,
        reviewed_at=None,
        reviewer_note=None,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.student_id = student.id if student is not None else student_id
        self.availability = availability or "Flexible"
        self.experience = experience
        self.preferred_role = preferred_role
        self.status = status or "pending"
        self.qr_token = qr_token or secrets.token_urlsafe(32)
        self.reviewed_at = parse_datetime(reviewed_at)
        self.reviewer_note = reviewer_note
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def assignment(self):
        if self.id is None:
            return None
        return VolunteerAssignment.find_one(application_id=self.id)

    @property
    def attendance_key(self):
        return _make_attendance_key("V", self.id, self.qr_token)


class VolunteerAssignment(FirestoreModel):
    collection_name = "volunteer_assignments"
    _fields = ("application_id", "volunteer_role", "responsibilities", "assigned_at")

    def __init__(
        self,
        id=None,
        application_id=None,
        application=None,
        volunteer_role="",
        responsibilities=None,
        assigned_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.application_id = application.id if application is not None else application_id
        self.volunteer_role = volunteer_role
        self.responsibilities = responsibilities
        self.assigned_at = parse_datetime(assigned_at) or _utcnow()

    @property
    def application(self):
        return VolunteerApplication.get(self.application_id)


class VolunteerTask(FirestoreModel):
    collection_name = "volunteer_tasks"
    _fields = (
        "event_id",
        "assignment_id",
        "title",
        "description",
        "deadline",
        "status",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        assignment_id=None,
        assignment=None,
        title="",
        description=None,
        deadline=None,
        status="assigned",
        created_at=None,
        updated_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.assignment_id = assignment.id if assignment is not None else assignment_id
        self.title = title
        self.description = description
        self.deadline = parse_datetime(deadline, naive=True)
        self.status = status or "assigned"
        self.created_at = parse_datetime(created_at) or _utcnow()
        self.updated_at = parse_datetime(updated_at) or _utcnow()

    def save(self):
        self.updated_at = _utcnow()
        return super().save()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def assignment(self):
        return VolunteerAssignment.get(self.assignment_id)


class Attendance(FirestoreModel):
    collection_name = "attendance"
    _fields = (
        "event_id",
        "student_id",
        "registration_id",
        "volunteer_application_id",
        "checked_in_at",
        "method",
    )

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        student_id=None,
        student=None,
        registration_id=None,
        registration=None,
        volunteer_application_id=None,
        volunteer_application=None,
        checked_in_at=None,
        method="qr",
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.student_id = student.id if student is not None else student_id
        self.registration_id = registration.id if registration is not None else registration_id
        self.volunteer_application_id = (
            volunteer_application.id
            if volunteer_application is not None
            else volunteer_application_id
        )
        self.checked_in_at = parse_datetime(checked_in_at) or _utcnow()
        self.method = method or "qr"

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def registration(self):
        return EventRegistration.get(self.registration_id)

    @property
    def volunteer_application(self):
        return VolunteerApplication.get(self.volunteer_application_id)


class Notification(FirestoreModel):
    collection_name = "notifications"
    _fields = ("user_id", "title", "message", "link", "is_read", "created_at")

    def __init__(
        self,
        id=None,
        user_id=None,
        user=None,
        title="",
        message="",
        link=None,
        is_read=False,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.user_id = user.id if user is not None else user_id
        self.title = title
        self.message = message
        self.link = link
        self.is_read = bool(is_read)
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def user(self):
        return User.get(self.user_id)


class Certificate(FirestoreModel):
    collection_name = "certificates"
    _fields = (
        "certificate_id",
        "recipient_id",
        "event_id",
        "certificate_type",
        "issue_date",
        "pdf_path",
        "is_valid",
        "issued_by",
        "created_at",
    )

    def __init__(
        self,
        id=None,
        certificate_id="",
        recipient_id=None,
        recipient=None,
        event_id=None,
        event=None,
        certificate_type="participation",
        issue_date=None,
        pdf_path=None,
        is_valid=True,
        issued_by=None,
        issuer=None,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.certificate_id = certificate_id
        self.recipient_id = recipient.id if recipient is not None else recipient_id
        self.event_id = event.id if event is not None else event_id
        self.certificate_type = certificate_type
        self.issue_date = parse_date(issue_date) or _utcnow().date()
        self.pdf_path = pdf_path
        self.is_valid = bool(is_valid)
        self.issued_by = issuer.id if issuer is not None else issued_by
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def recipient(self):
        return User.get(self.recipient_id)

    @property
    def issuer(self):
        return User.get(self.issued_by)

    @property
    def event(self):
        return Event.get(self.event_id)


class Feedback(FirestoreModel):
    collection_name = "feedback"
    _fields = ("event_id", "student_id", "rating", "suggestions", "is_anonymous", "created_at")

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        student_id=None,
        student=None,
        rating=5,
        suggestions=None,
        is_anonymous=False,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.student_id = student.id if student is not None else student_id
        self.rating = int(rating)
        self.suggestions = suggestions
        self.is_anonymous = bool(is_anonymous)
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def student(self):
        return User.get(self.student_id)


class EventGallery(FirestoreModel):
    collection_name = "event_galleries"
    _fields = ("event_id", "image_path", "caption", "uploaded_by", "created_at")

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        image_path="",
        caption=None,
        uploaded_by=None,
        uploader=None,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.image_path = image_path
        self.caption = caption
        self.uploaded_by = uploader.id if uploader is not None else uploaded_by
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def uploader(self):
        return User.get(self.uploaded_by)


class VolunteerHours(FirestoreModel):
    collection_name = "volunteer_hours"
    _fields = ("student_id", "event_id", "hours", "note", "recorded_by", "recorded_at")

    def __init__(
        self,
        id=None,
        student_id=None,
        student=None,
        event_id=None,
        event=None,
        hours=0,
        note=None,
        recorded_by=None,
        recorder=None,
        recorded_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.student_id = student.id if student is not None else student_id
        self.event_id = event.id if event is not None else event_id
        self.hours = parse_decimal(hours)
        self.note = note
        self.recorded_by = recorder.id if recorder is not None else recorded_by
        self.recorded_at = parse_datetime(recorded_at) or _utcnow()

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def recorder(self):
        return User.get(self.recorded_by)


class EventBudget(FirestoreModel):
    collection_name = "event_budgets"
    _fields = ("event_id", "allocated_amount", "created_at")

    def __init__(
        self,
        id=None,
        event_id=None,
        event=None,
        allocated_amount=0,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.event_id = event.id if event is not None else event_id
        self.allocated_amount = parse_decimal(allocated_amount)
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def expenses(self):
        return EventExpense.where(budget_id=self.id) if self.id is not None else []


class EventExpense(FirestoreModel):
    collection_name = "event_expenses"
    _fields = ("budget_id", "category", "description", "amount", "expense_date", "created_at")

    def __init__(
        self,
        id=None,
        budget_id=None,
        budget=None,
        category="",
        description=None,
        amount=0,
        expense_date=None,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.budget_id = budget.id if budget is not None else budget_id
        self.category = category
        self.description = description
        self.amount = parse_decimal(amount)
        self.expense_date = parse_date(expense_date)
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def budget(self):
        return EventBudget.get(self.budget_id)


class Resource(FirestoreModel):
    collection_name = "resources"
    _fields = ("name", "resource_type", "location", "capacity", "is_active")

    def __init__(
        self,
        id=None,
        name="",
        resource_type="",
        location=None,
        capacity=None,
        is_active=True,
        **kwargs,
    ):
        super().__init__(id=id)
        self.name = name
        self.resource_type = resource_type
        self.location = location
        self.capacity = int(capacity) if capacity is not None else None
        self.is_active = bool(is_active)

    @property
    def bookings(self):
        return ResourceBooking.where(resource_id=self.id) if self.id is not None else []


class ResourceBooking(FirestoreModel):
    collection_name = "resource_bookings"
    _fields = (
        "resource_id",
        "event_id",
        "requester_id",
        "purpose",
        "booking_date",
        "start_time",
        "end_time",
        "status",
        "created_at",
    )

    def __init__(
        self,
        id=None,
        resource_id=None,
        resource=None,
        event_id=None,
        event=None,
        requester_id=None,
        requester=None,
        purpose="",
        booking_date=None,
        start_time=None,
        end_time=None,
        status="confirmed",
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.resource_id = resource.id if resource is not None else resource_id
        self.event_id = event.id if event is not None else event_id
        self.requester_id = requester.id if requester is not None else requester_id
        self.purpose = purpose
        self.booking_date = parse_date(booking_date)
        self.start_time = parse_time(start_time)
        self.end_time = parse_time(end_time)
        self.status = status or "confirmed"
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def resource(self):
        return Resource.get(self.resource_id)

    @property
    def event(self):
        return Event.get(self.event_id)

    @property
    def requester(self):
        return User.get(self.requester_id)


class StudentInterest(FirestoreModel):
    collection_name = "student_interests"
    _fields = ("student_id", "category_id", "created_at")

    def __init__(
        self,
        id=None,
        student_id=None,
        student=None,
        category_id=None,
        category=None,
        created_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.student_id = student.id if student is not None else student_id
        self.category_id = category.id if category is not None else category_id
        self.created_at = parse_datetime(created_at) or _utcnow()

    @property
    def student(self):
        return User.get(self.student_id)

    @property
    def category(self):
        return EventCategory.get(self.category_id)


class User(UserMixin, FirestoreModel):
    collection_name = "users"
    _fields = (
        "full_name",
        "email",
        "password_hash",
        "student_id",
        "phone",
        "role_id",
        "department_id",
        "is_active",
        "created_at",
        "updated_at",
    )

    def __init__(
        self,
        id=None,
        full_name="",
        email="",
        password_hash="",
        student_id=None,
        phone=None,
        role_id=None,
        role=None,
        department_id=None,
        department=None,
        is_active=True,
        created_at=None,
        updated_at=None,
        **kwargs,
    ):
        super().__init__(id=id)
        self.full_name = full_name
        self.email = (email or "").strip().lower()
        self.password_hash = password_hash
        self.student_id = student_id
        self.phone = phone
        self.role_id = role.id if role is not None else role_id
        self.department_id = department.id if department is not None else department_id
        self._is_active = bool(is_active)
        self.created_at = parse_datetime(created_at) or _utcnow()
        self.updated_at = parse_datetime(updated_at) or _utcnow()

    @property
    def is_active(self):
        return self._is_active

    @is_active.setter
    def is_active(self, value):
        self._is_active = bool(value)

    def get_id(self):
        return str(self.id) if self.id is not None else None

    def save(self):
        self.updated_at = _utcnow()
        return super().save()

    @property
    def role(self):
        return Role.get(self.role_id)

    @property
    def department(self):
        return Department.get(self.department_id)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def role_name(self):
        role_obj = self.role
        return role_obj.name if role_obj else None


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)
