from flask_wtf import FlaskForm
from wtforms import PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError

from app.models import User


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    submit = SubmitField("Sign in")


class RegistrationForm(FlaskForm):
    full_name = StringField("Full name", validators=[DataRequired(), Length(min=2, max=120)])
    email = StringField("College email", validators=[DataRequired(), Email(), Length(max=180)])
    student_id = StringField("Student ID", validators=[DataRequired(), Length(min=3, max=50)])
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=12, message="Use at least 12 characters."),
        ],
    )
    confirm_password = PasswordField(
        "Confirm password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    department_id = SelectField("Department", coerce=int, validators=[DataRequired()])
    submit = SubmitField("Create account")

    def validate_email(self, field):
        if User.find_one(email=field.data.strip().lower()):
            raise ValidationError("An account with this email already exists.")

    def validate_student_id(self, field):
        if User.find_one(student_id=field.data.strip()):
            raise ValidationError("This student ID is already registered.")
