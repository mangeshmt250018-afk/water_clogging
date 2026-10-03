from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, SelectField, HiddenField, TextAreaField
from wtforms.validators import DataRequired, Email, Length
from flask_wtf.file import FileField, FileRequired, FileAllowed

class signupform(FlaskForm):
    username = StringField(
        'Enter the Username',
        validators=[
            DataRequired(),
            Length(min=2, max=20, message="Username must be between 2 and 20 characters.")
        ]
    )
    email = StringField(
        'Enter the email',
        validators=[
            DataRequired(),
            Email(message="Please enter a valid email address."),
            Length(max=100, message="Email must be under 100 characters.")
        ]
    )
    password = PasswordField(
        'Enter your password',
        validators=[
            DataRequired(),
            Length(min=8, max=100, message="Password must be between 8 and 100 characters.")
        ]
    )
    submit = SubmitField('Submit')

class loginform(FlaskForm):
    email = StringField(
        'Enter the email',
        validators=[
            DataRequired(),
            Email(message="Please enter a valid email address."),
            Length(max=100, message="Email must be under 100 characters.")
        ]
    )
    password = PasswordField(
        'Enter your password',
        validators=[
            DataRequired(),
            Length(min=8, max=100, message="Password must be between 8 and 100 characters.")
        ]
    )
    submit = SubmitField('Submit')

class reportform(FlaskForm):
    images = FileField(
        "Upload the image",
        validators=[
            FileRequired(),
            FileAllowed(["jpg", "jpeg", "png"], "Images only!")
        ]
    )
    cause = SelectField(
        "Choose the reason",
        choices=[
            ("", "Select the cause"),
            ("Poor drainage system", "Poor drainage system"),
            ("Heavy rainfall", "Heavy rainfall"),
            ("Blocked sewers", "Blocked sewers"),
            ("Damaged water pipe line", "Damaged water pipe line"),
            ("Other", "Other"),
        ],
        validators=[DataRequired(message="Please choose a cause.")]
    )
    latitude = HiddenField()
    longitude = HiddenField()
    description = StringField(
        "Describe the Problem",
        validators=[
            Length(max=500, message="Description must be under 500 characters.")
        ]
    )
    submit = SubmitField('Submit')

class CommentForm(FlaskForm):
    content = TextAreaField(
        'Add a comment...',
        validators=[
            DataRequired(message="Comment cannot be empty."),
            Length(max=2000, message="Comment must be under 2000 characters.")
        ]
    )
    submit = SubmitField('Post Comment')

class StatusUpdateForm(FlaskForm):
    status = SelectField(
        'Update Status',
        choices=[
            ("Submitted", "Submitted"),
            ("Under Review", "Under Review"),
            ("Assigned", "Assigned"),
            ("In Progress", "In Progress"),
            ("Resolved", "Resolved"),
            ("Closed", "Closed"),
            ("Reopened", "Reopened"),
        ],
        validators=[DataRequired(message="Please select a valid status.")]
    )
    submit = SubmitField('Update Status')