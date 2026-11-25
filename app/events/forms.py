from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    TextAreaField,
    TimeField,
    SubmitField,
)
from wtforms.validators import DataRequired, InputRequired, Length, NumberRange, Optional


class EventForm(FlaskForm):
    title = StringField("Event title", validators=[DataRequired(), Length(max=160)])
    description = TextAreaField("Description", validators=[DataRequired(), Length(min=20)])
    category_id = SelectField("Category", coerce=int, validators=[DataRequired()])
    department_id = SelectField("Department", coerce=int, choices=[(0, "All Departments")])
    club_id = SelectField("College club", coerce=int, choices=[(0, "None")])
    venue = StringField("Venue", validators=[DataRequired(), Length(max=160)])
    organizer = StringField("Organizer", validators=[DataRequired(), Length(max=160)])
    event_date = DateField("Event date", validators=[DataRequired()])
    end_date = DateField("End date (optional)", validators=[Optional()])
    start_time = TimeField("Start time", validators=[DataRequired()])
    end_time = TimeField("End time (optional)", validators=[Optional()])
    registration_deadline = StringField(
        "Registration deadline",
        validators=[DataRequired(), Length(max=25)],
    )
    volunteer_requirement = IntegerField(
        "Volunteer requirement",
        validators=[InputRequired(), NumberRange(min=0, max=10000)],
        default=0,
    )
    registration_compulsory = BooleanField("Registration compulsory", default=False)
    poster = FileField(
        "Event poster",
        validators=[FileAllowed(["jpg", "jpeg", "png", "webp"], "Upload a JPG, PNG, or WebP image.")],
    )
    submit = SubmitField("Save event")


class VolunteerApplicationForm(FlaskForm):
    preferred_role = SelectField(
        "Preferred role",
        choices=[
            ("Registration Desk", "Registration Desk"),
            ("Technical Support", "Technical Support"),
            ("Stage Management", "Stage Management"),
            ("Guest Coordination", "Guest Coordination"),
            ("Event Photography", "Event Photography"),
        ],
    )
    experience = TextAreaField("Relevant experience")
    submit = SubmitField("Apply for volunteering")
