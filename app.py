from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap5
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship, joinedload, selectinload
from sqlalchemy import Integer, String, Boolean, Float, DateTime
from sqlalchemy.exc import IntegrityError
from form import reportform, signupform, loginform, CommentForm, StatusUpdateForm
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user, login_required
from flask_migrate import Migrate
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from supabase import create_client
from verification import confirm_verification_token, generate_verification_token, send_verification_email
from datetime import datetime, timezone, timedelta
from functools import wraps
from urllib.parse import urlparse, urljoin
import bleach
import uuid
import os 
import math
import io
from PIL import Image
from PIL.Image import DecompressionBombError
from flask_mail import Mail  
from flask_wtf.csrf import CSRFProtect

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone(timedelta(hours=5, minutes=30), name="IST")

def to_ist(dt):
    """Convert a UTC datetime (aware or naive UTC) to timezone-aware IST."""
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def format_ist(dt, fmt="%b %d, %Y at %I:%M %p IST"):
    """Format a datetime as an IST string for user display."""
    ist_dt = to_ist(dt)
    if not ist_dt:
        return ""
    return ist_dt.strftime(fmt)  

load_dotenv()

# Pillow Decompression Bomb protection configurations
# Limit maximum image size to 16 Megapixels to prevent memory exhaustion
Image.MAX_IMAGE_PIXELS = 16777216

is_testing = os.environ.get("TESTING", "False").lower() in ("true", "1", "yes")
is_debug = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")

# Verify Supabase credentials exist
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
if not supabase_url or not supabase_key:
    if not (is_testing or is_debug):
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY environment variables are required in production!")
    supabase_url = supabase_url or "https://placeholder-project.supabase.co"
    supabase_key = supabase_key or "placeholder-anon-key"

supabase = create_client(supabase_url, supabase_key)

app = Flask(__name__)
app.config.from_pyfile('config.py')

Bootstrap5(app)
mail = Mail(app) 
csrf = CSRFProtect(app)

# Configure Flask-Limiter for rate-limiting
storage_uri = app.config.get("RATELIMIT_STORAGE_URL") or os.environ.get("RATELIMIT_STORAGE_URL") or "memory://"
if storage_uri == "memory://" and not (is_testing or is_debug):
    app.logger.warning(
        "RATELIMIT_STORAGE_URL is not set. In-memory storage is active. "
        "For multi-worker production deployments (e.g. Gunicorn/Redis), set RATELIMIT_STORAGE_URL."
    )

limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri=storage_uri
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_message = "You have to login first to report."
login_manager.login_view = 'login'

class Base(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=Base)
db.init_app(app)
migrate = Migrate(app, db)

# Allowed report statuses in sequential workflow order
ALLOWED_STATUSES = [
    "Submitted",
    "Under Review",
    "Assigned",
    "In Progress",
    "Resolved",
    "Closed",
    "Reopened"
]

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password: Mapped[str] = mapped_column(String, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    last_verification_sent: Mapped[datetime] = mapped_column(DateTime, nullable=True)
    reports = relationship("Report", back_populates="author", cascade="all, delete-orphan")
    comments = relationship("Comment", back_populates="author", cascade="all, delete-orphan")

    @property
    def report(self):
        return self.reports

class Report(db.Model):
    __tablename__ = 'reports'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('users.id'), nullable=False)
    author = relationship("User", back_populates="reports")
    cause: Mapped[str] = mapped_column(String, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    image_path: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="Submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    comments = relationship("Comment", back_populates="report", cascade="all, delete-orphan", order_by="Comment.created_at.asc()")

class Comment(db.Model):
    __tablename__ = 'comments'
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    report_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('reports.id', ondelete='CASCADE'), nullable=False)
    author_id: Mapped[int] = mapped_column(Integer, db.ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    content: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    
    report = relationship("Report", back_populates="comments")
    author = relationship("User", back_populates="comments")

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))

def is_safe_url(target):
    if not target:
        return False
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def get_safe_redirect(target, default_endpoint='index', **kwargs):
    if target and is_safe_url(target):
        return target
    return url_for(default_endpoint, **kwargs)

def is_authority(user):
    if not user or not user.is_authenticated:
        return False
    configured_auth = app.config.get("GOVERNMENT_AUTHORITY_EMAIL")
    if not configured_auth:
        return False
    user_email = (user.email or "").strip().lower()
    return user_email == configured_auth.strip().lower()

def authority_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login', next=request.url))
        if not is_authority(current_user):
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

app.jinja_env.filters['to_ist'] = to_ist
app.jinja_env.filters['format_ist'] = format_ist

@app.context_processor
def inject_template_globals():
    
    return dict(
        is_authority=is_authority(current_user),
        allowed_statuses=ALLOWED_STATUSES,
        to_ist=to_ist,
        format_ist=format_ist
    )

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'blockquote', 'a']
ALLOWED_ATTRIBUTES = {
    'a': ['href', 'title', 'target', 'rel']
}
ALLOWED_PROTOCOLS = ['http', 'https']

def sanitize_comment_html(raw_html: str) -> str:
    if not raw_html:
        return ""
    cleaned = bleach.clean(
        raw_html,
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        protocols=ALLOWED_PROTOCOLS,
        strip=True
    )
    cleaned = bleach.linkify(
        cleaned,
        callbacks=[
            lambda attrs, new: {
                **attrs,
                (None, 'rel'): 'noopener noreferrer',
                (None, 'target'): '_blank'
            }
        ]
    )
    return cleaned

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
    
    if os.environ.get("ENABLE_HSTS", "False").lower() in ("true", "1", "yes") or (not (is_testing or is_debug)):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        
    csp_directives = (
        "default-src 'self'; "
        "script-src 'self' https://unpkg.com https://cdn.jsdelivr.net; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://unpkg.com https://cdn.jsdelivr.net; "
        "img-src 'self' data: https://*.openstreetmap.org https://*.supabase.co https://unpkg.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "connect-src 'self' https://*.supabase.co; "
        "frame-ancestors 'self'; "
        "form-action 'self'; "
        "base-uri 'self';"
    )
    response.headers['Content-Security-Policy'] = csp_directives
    return response


@app.errorhandler(400)
def bad_request_error(e):
    return render_template("error.html", code=400, message="Bad Request. The server could not understand your request."), 400

@app.errorhandler(401)
def unauthorized_error(e):
    return render_template("error.html", code=401, message="Unauthorized. You must login to view this resource."), 401

@app.errorhandler(403)
def forbidden_error(e):
    return render_template("error.html", code=403, message="Forbidden. You do not have permission to access this resource."), 403

@app.errorhandler(404)
def not_found_error(e):
    return render_template("error.html", code=404, message="Page Not Found. The requested URL was not found on this server."), 404

@app.errorhandler(405)
def method_not_allowed_error(e):
    return render_template("error.html", code=405, message="Method Not Allowed. The HTTP method used is not supported for this route."), 405

@app.errorhandler(413)
def request_entity_too_large(e):
    return render_template("error.html", code=413, message="File Too Large. Uploads must be smaller than 5 MB."), 413

@app.errorhandler(429)
def ratelimit_error(e):
    return render_template("error.html", code=429, message="Too Many Requests. Please wait and try again later."), 429

@app.errorhandler(500)
def internal_server_error(e):
    return render_template("error.html", code=500, message="An internal server error occurred. Our engineers are investigating."), 500

def validate_and_sanitize_image(image_file):
    try:
        file_data = image_file.read()
        if len(file_data) > 5 * 1024 * 1024:
            raise ValueError("The uploaded file exceeds the 5MB size limit.")
        if not file_data:
            raise ValueError("No file contents detected.")

      
        try:
            img = Image.open(io.BytesIO(file_data))
            img.verify()
        except DecompressionBombError:
            raise ValueError("Image validation failed: Decompression bomb detected (excessive dimensions).")
        except Exception:
            raise ValueError("The uploaded file is not a valid image or is corrupted.")

        img = Image.open(io.BytesIO(file_data))
        
        width, height = img.size
        if width * height > 16777216:
            raise ValueError("Image dimensions exceed the maximum 16 Megapixel limit.")
        if width > 4096 or height > 4096:
            raise ValueError("Image width or height exceeds the maximum 4096px limit.")

        real_format = img.format
        if real_format not in ("JPEG", "PNG"):
            raise ValueError("Unsupported format. Only JPEG and PNG formats are allowed.")

        if real_format == "JPEG":
            content_type = "image/jpeg"
            extension = ".jpg"
        else:
            content_type = "image/png"
            extension = ".png"

        output_buffer = io.BytesIO()
        img.save(output_buffer, format=real_format)
        sanitized_bytes = output_buffer.getvalue()

        return sanitized_bytes, content_type, extension
    except ValueError:
        raise
    except Exception as e:
        app.logger.error(f"Pillow image parsing failure: {e}")
        raise ValueError("Image processing failed due to an internal validation error.")

def validate_location(latitude_str, longitude_str):
    if not latitude_str or not longitude_str:
        raise ValueError("Please allow location access to submit a report.")
    
    try:
        lat = float(latitude_str)
        lng = float(longitude_str)
    except ValueError:
        raise ValueError("Received invalid coordinates.")

    if not math.isfinite(lat) or not math.isfinite(lng):
        raise ValueError("Coordinates must be finite real numbers.")

    if not (-90.0 <= lat <= 90.0):
        raise ValueError("Latitude must be between -90 and 90 degrees.")

    if not (-180.0 <= lng <= 180.0):
        raise ValueError("Longitude must be between -180 and 180 degrees.")

    return lat, lng

@app.route('/')
def index():
    reports = db.session.execute(
        db.select(Report)
        .options(joinedload(Report.author))
        .order_by(Report.id.desc())
        .limit(100)
    ).scalars().all()

    reports_list = []
    for r in reports:
        img_path = r.image_path
        
        if img_path and img_path.startswith('reports/'):
            try:
                img_path = supabase.storage.from_("water clogging images").get_public_url(img_path)
            except Exception as e:
                app.logger.error(f"Supabase public url retrieval failed: {e}")
                img_path = None

        reports_list.append({
            'id': r.id,
            'latitude': r.latitude,
            'longitude': r.longitude,
            'cause': r.cause,
            'description': r.description,
            'image_path': img_path,
            'author': r.author.name if r.author else "Anonymous",
            'status': r.status or "Submitted",
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M') if r.created_at else ''
        })

    total_reports = db.session.scalar(db.select(db.func.count(Report.id))) or 0

    return render_template('index.html', reports=reports_list, total_reports=total_reports)

@app.route('/reports')
def reports_list():
    status_filter = request.args.get('status', '').strip()
    cause_filter = request.args.get('cause', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = 18
    
    query = db.select(Report).options(joinedload(Report.author), selectinload(Report.comments)).order_by(Report.id.desc())
    if status_filter and status_filter in ALLOWED_STATUSES:
        query = query.where(Report.status == status_filter)
    if cause_filter:
        query = query.where(Report.cause == cause_filter)
        
    pagination = db.paginate(query, page=page, per_page=per_page, error_out=False)
    reports = pagination.items
    
    for r in reports:
        if r.image_path and r.image_path.startswith('reports/'):
            try:
                r.public_image_url = supabase.storage.from_("water clogging images").get_public_url(r.image_path)
            except Exception as e:
                app.logger.error(f"Supabase public url retrieval failed for report {r.id}: {e}")
                r.public_image_url = None
        else:
            r.public_image_url = r.image_path
            
    return render_template(
        'reports.html',
        reports=reports,
        pagination=pagination,
        status_filter=status_filter,
        cause_filter=cause_filter
    )

@app.route('/report/<int:report_id>')
def report_detail(report_id):
    report = db.session.execute(
        db.select(Report)
        .options(
            joinedload(Report.author),
            selectinload(Report.comments).joinedload(Comment.author)
        )
        .where(Report.id == report_id)
    ).scalar()

    if not report:
        abort(404)

    public_image_url = report.image_path
    if public_image_url and public_image_url.startswith('reports/'):
        try:
            public_image_url = supabase.storage.from_("water clogging images").get_public_url(public_image_url)
        except Exception as e:
            app.logger.error(f"Supabase public url retrieval failed: {e}")
            public_image_url = None

    comment_form = CommentForm()
    status_form = StatusUpdateForm(status=report.status) if is_authority(current_user) else None

    return render_template(
        'report_detail.html',
        report=report,
        public_image_url=public_image_url,
        comment_form=comment_form,
        status_form=status_form
    )

@app.route('/report/<int:report_id>/comment', methods=['POST'])
@login_required
@limiter.limit("10 per minute; 50 per hour", methods=["POST"])
def add_comment(report_id):
    report = db.session.get(Report, report_id)
    if not report:
        abort(404)

    form = CommentForm()
    if form.validate_on_submit():
        raw_content = form.content.data.strip()
        sanitized_content = sanitize_comment_html(raw_content)

        if not sanitized_content:
            flash("Comment content cannot be empty.")
            return redirect(url_for('report_detail', report_id=report_id))

        comment = Comment(
            report_id=report.id,
            author_id=current_user.id,
            content=sanitized_content,
            created_at=datetime.now(timezone.utc)
        )
        try:
            db.session.add(comment)
            db.session.commit()
            flash("Comment posted successfully.")
        except Exception:
            db.session.rollback()
            app.logger.exception("Failed to post comment")
            flash("We couldn't save your comment right now. Please try again.")
    else:
        for field, errors in form.errors.items():
            for err in errors:
                flash(f"Comment error: {err}")

    return redirect(url_for('report_detail', report_id=report_id))

@app.route('/authority/reports')
@authority_required
def authority_dashboard():
    status_filter = request.args.get('status', '').strip()
    
    query = db.select(Report).options(joinedload(Report.author), selectinload(Report.comments)).order_by(Report.id.desc())
    if status_filter and status_filter in ALLOWED_STATUSES:
        query = query.where(Report.status == status_filter)
        
    all_reports = db.session.execute(query).scalars().all()

    # Calculate status count aggregates for metric cards
    stats = {status: 0 for status in ALLOWED_STATUSES}
    total_count = 0
    all_unfiltered = db.session.execute(db.select(Report.status)).scalars().all()
    for s in all_unfiltered:
        total_count += 1
        if s in stats:
            stats[s] += 1

    for r in all_reports:
        if r.image_path and r.image_path.startswith('reports/'):
            try:
                r.public_image_url = supabase.storage.from_("water clogging images").get_public_url(r.image_path)
            except Exception as e:
                app.logger.error(f"Supabase public url retrieval failed: {e}")
                r.public_image_url = None
        else:
            r.public_image_url = r.image_path

    return render_template(
        'authority_dashboard.html',
        reports=all_reports,
        stats=stats,
        total_count=total_count,
        status_filter=status_filter
    )

@app.route('/authority/reports/<int:report_id>/status', methods=['POST'])
@authority_required
@limiter.limit("20 per minute; 100 per hour", methods=["POST"])
def update_report_status(report_id):
    report = db.session.get(Report, report_id)
    if not report:
        abort(404)

    new_status = request.form.get("status", "").strip()
    if new_status not in ALLOWED_STATUSES:
        flash(f"Invalid status: '{new_status}'. Please select a valid status.")
        redirect_target = get_safe_redirect(request.referrer, default_endpoint='authority_dashboard')
        return redirect(redirect_target)

    report.status = new_status
    try:
        db.session.commit()
        flash(f"Report #{report.id} status updated to '{new_status}'.")
    except Exception:
        db.session.rollback()
        app.logger.exception(f"Failed to update status for report #{report_id}")
        flash("Failed to update status due to a server error.")

    redirect_target = get_safe_redirect(request.referrer, default_endpoint='report_detail', report_id=report.id)
    return redirect(redirect_target)

@app.route('/report', methods=['GET', 'POST'])
@login_required
@limiter.limit("5 per minute; 20 per day", methods=["POST"])
def report():
    image_path = url_for('static', filename='images/report.jpg')
    current_page = "report"
    form = reportform()

    if form.validate_on_submit():
        # Validate geolocation bounds
        try:
            latitude, longitude = validate_location(form.latitude.data, form.longitude.data)
        except ValueError as err:
            flash(str(err))
            return render_template("form.html", form=form, current_page=current_page, img=image_path)

        # Validate image file and process decompression constraints
        image_file = form.images.data
        try:
            sanitized_data, content_type, extension = validate_and_sanitize_image(image_file)
        except ValueError as err:
            flash(str(err))
            return render_template("form.html", form=form, current_page=current_page, img=image_path)

        # database path
        filename = f"{uuid.uuid4()}{extension}"
        file_path = f"reports/{filename}"

        try:
            supabase.storage.from_("water clogging images").upload(
                path=file_path,
                file=sanitized_data,
                file_options={"content-type": content_type}
            )
        except Exception as e:
            app.logger.error(f"Supabase upload failed: {e}")
            flash("We couldn't upload your image right now. Please try again.")
            return render_template("form.html", form=form, current_page=current_page, img=image_path)

    
        report_record = Report(
            author_id=current_user.id,
            image_path=file_path,
            cause=form.cause.data,
            description=form.description.data,
            latitude=latitude,
            longitude=longitude,
            status="Submitted",
            created_at=datetime.now(timezone.utc)
        )

        try:
            db.session.add(report_record)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Database commit failed, initiating Supabase storage rollback")
            
            try:
                supabase.storage.from_("water clogging images").remove([file_path])
            except Exception as rm_err:
                app.logger.error(f"Failed to delete orphaned Supabase object {file_path}: {rm_err}")
            
            flash("We couldn't save your report right now. Please try again.")
            return render_template("form.html", form=form, current_page=current_page, img=image_path)

        return redirect(url_for('index'))

    return render_template('form.html', form=form, img=image_path, current_page=current_page)

@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("5 per minute", methods=["POST"])
def login():
    form = loginform()
    current_page = "login"
    image_path = url_for('static', filename='images/signup-bg.jpg')
    
   
    dummy_hash = generate_password_hash("timing_safety_placeholder_password", method='pbkdf2:sha256')

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        password = form.password.data
        
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()

        if user:
            valid_pwd = check_password_hash(user.password, password)
        else:
            check_password_hash(dummy_hash, password)
            valid_pwd = False

        if user and valid_pwd:
            if not user.is_verified:
                flash("Please verify your email before logging in.")
                return redirect(url_for('login'))
            
            login_user(user=user)
            next_url = request.args.get('next')
            redirect_target = get_safe_redirect(next_url, default_endpoint='index')
            return redirect(redirect_target)
        else:
            flash("Invalid email or password.")
            return redirect(url_for('login'))
            
    return render_template('form.html', form=form, current_page=current_page, img=image_path)

@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("3 per hour", methods=["POST"])
def register():
    current_page = "signup"
    form = signupform()
    image_path = url_for('static', filename='images/register-bg.jpg')

    if form.validate_on_submit():
        email = form.email.data.strip().lower()
        
        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        if user:
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))

        new_user = User(
            name=form.username.data,
            email=email,
            password=generate_password_hash(form.password.data, method='pbkdf2:sha256', salt_length=8),
            last_verification_sent=datetime.now(timezone.utc)
        )

        try:
            db.session.add(new_user)
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for("login"))
        except Exception:
            db.session.rollback()
            app.logger.exception("Database registration error occurred")
            flash("Registration failed due to a database error. Please try again.")
            return render_template('form.html', form=form, img=image_path, current_page=current_page)

        token = generate_verification_token(email)
        verify_url = url_for('verify_email', token=token, _external=True)

        try:
            send_verification_email(email_to=email, verify_url=verify_url)
        except Exception:
            app.logger.exception(f"SMTP delivery failed for {email}")
            flash("Account registered successfully, but we were unable to send your verification email. Please request a verification link below.")
            return redirect(url_for('resend_verification'))

        verification_bg = url_for('static', filename='images/verification-bg.jpg')
        return render_template('verification.html', email=email, img=verification_bg)

    return render_template('form.html', form=form, img=image_path, current_page=current_page)

@app.route("/verify/<token>")
def verify_email(token):
    email = confirm_verification_token(token)
    if not email:
        return render_template("error.html", code=400, message="The verification link is invalid or has expired."), 400

    user = db.session.execute(db.select(User).where(User.email == email)).scalar()
    if user and not user.is_verified:
        try:
            user.is_verified = True
            db.session.commit()
            login_user(user)
            return redirect(url_for('index'))
        except Exception:
            db.session.rollback()
            app.logger.exception("Failed to mark user as verified")
            flash("Verification failed due to a server error. Please try again.")
            return redirect(url_for('login'))
    else:
        flash("Account already verified. Try to login")
        return redirect(url_for('login'))

@app.route('/resend-verification', methods=['GET', 'POST'])
@limiter.limit("3 per minute; 10 per hour", methods=["POST"])
def resend_verification():
    """
    Endpoint allowing unverified users to request a new verification email,
    enforcing a persistent 60-second cooldown rate limit.
    """
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        if not email:
            flash("Please enter a valid email address.")
            return render_template('resend_verification.html')

        user = db.session.execute(db.select(User).where(User.email == email)).scalar()
        
        generic_msg = "If the email is registered and unverified, a verification link has been sent."
        
        if not user:
            flash(generic_msg)
            return redirect(url_for('login'))

        if user.is_verified:
            flash("Account already verified. Please log in.")
            return redirect(url_for('login'))

        if user.last_verification_sent:
            time_since_sent = datetime.now(timezone.utc) - user.last_verification_sent.replace(tzinfo=timezone.utc)
            if time_since_sent.total_seconds() < 60:
                flash("Please wait a minute before requesting another verification email.")
                return render_template('resend_verification.html', email=email)

        # Update cooldown timestamp
        try:
            user.last_verification_sent = datetime.now(timezone.utc)
            db.session.commit()
        except Exception:
            db.session.rollback()
            app.logger.exception("Failed to update last_verification_sent cooldown")
            flash("An error occurred. Please try again.")
            return render_template('resend_verification.html')

        token = generate_verification_token(email)
        verify_url = url_for('verify_email', token=token, _external=True)

        try:
            send_verification_email(email_to=email, verify_url=verify_url)
        except Exception:
            app.logger.exception(f"Resend verification email failed for {email}")
            flash("We were unable to send your verification email right now. Please try again in a moment.")
            return render_template('resend_verification.html', email=email)

        flash(generic_msg)
        return redirect(url_for('login'))

    return render_template('resend_verification.html')

@app.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    return redirect(url_for('index'))

if __name__ == '__main__':
    debug_mode = os.environ.get("FLASK_DEBUG", "False").lower() in ("true", "1", "yes")
    app.run(debug=debug_mode)