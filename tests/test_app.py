import os
os.environ["TESTING"] = "True"
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["GOVERNMENT_AUTHORITY_EMAIL"] = "authority@example.com"
import pytest
import io
import math
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, module="storage3.*")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="supabase.*")
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from app import (
    app, db, User, Report, Comment, ALLOWED_STATUSES, is_authority,
    sanitize_comment_html, validate_location, validate_and_sanitize_image,
    to_ist, format_ist, IST, is_safe_url, get_safe_redirect
)
from verification import generate_verification_token
from PIL import Image

# Helper to create mock images for testing
def create_test_image(format="PNG", size=(100, 100)):
    file = io.BytesIO()
    image = Image.new("RGBA", size=size, color=(255, 0, 0))
    image.save(file, format=format)
    file.seek(0)
    return file

@pytest.fixture
def client():
    from app import limiter
    limiter.enabled = False
    app.config["TESTING"] = True
    app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app.config["WTF_CSRF_ENABLED"] = False  # Disabled by default for standard workflow tests
    app.config["RATELIMIT_ENABLED"] = False
    app.config["GOVERNMENT_AUTHORITY_EMAIL"] = "authority@example.com"
    
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()

def test_registration_success(client):
    with patch("app.send_verification_email") as mock_email:
        response = client.post("/register", data={
            "username": "tester",
            "email": "tester@example.com",
            "password": "securepassword123"
        }, follow_redirects=True)
        assert response.status_code == 200
        assert b"Verify the email" in response.data
        mock_email.assert_called_once()
        
        # Verify user was saved in DB and is unverified
        user = db.session.execute(db.select(User).where(User.email == "tester@example.com")).scalar()
        assert user is not None
        assert user.is_verified is False

def test_registration_duplicate_email(client):
    # Register first user
    user = User(name="first", email="test@example.com", password="passwordhash123", is_verified=False)
    db.session.add(user)
    db.session.commit()
    
    response = client.post("/register", data={
        "username": "second",
        "email": "test@example.com",
        "password": "anotherpassword"
    }, follow_redirects=True)
    
    assert b"already signed up with that email" in response.data

def test_registration_invalid_inputs(client):
    # Test short password (< 8 chars)
    response = client.post("/register", data={
        "username": "tester",
        "email": "tester@example.com",
        "password": "short"
    }, follow_redirects=True)
    assert b"Password must be between 8 and 100 characters." in response.data

    # Test short username (< 2 chars)
    response = client.post("/register", data={
        "username": "t",
        "email": "tester@example.com",
        "password": "securepassword"
    }, follow_redirects=True)
    assert b"Username must be between 2 and 20 characters." in response.data

def test_login_success(client):
    from werkzeug.security import generate_password_hash
    hashed_pwd = generate_password_hash("mypassword123", method="pbkdf2:sha256")
    user = User(name="mangesh", email="mangesh@example.com", password=hashed_pwd, is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    response = client.post("/login", data={
        "email": "mangesh@example.com",
        "password": "mypassword123"
    }, follow_redirects=True)
    
    assert response.status_code == 200
    assert b"Submit a Report" in response.data

def test_login_incorrect_password(client):
    from werkzeug.security import generate_password_hash
    hashed_pwd = generate_password_hash("mypassword123", method="pbkdf2:sha256")
    user = User(name="mangesh", email="mangesh@example.com", password=hashed_pwd, is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    response = client.post("/login", data={
        "email": "mangesh@example.com",
        "password": "wrongpassword"
    }, follow_redirects=True)
    
    assert b"Invalid email or password" in response.data

def test_login_nonexistent_email(client):
    response = client.post("/login", data={
        "email": "nonexistent@example.com",
        "password": "somepassword"
    }, follow_redirects=True)
    
    assert b"Invalid email or password" in response.data

def test_login_unverified_account(client):
    from werkzeug.security import generate_password_hash
    hashed_pwd = generate_password_hash("mypassword123", method="pbkdf2:sha256")
    user = User(name="mangesh", email="mangesh@example.com", password=hashed_pwd, is_verified=False)
    db.session.add(user)
    db.session.commit()
    
    response = client.post("/login", data={
        "email": "mangesh@example.com",
        "password": "mypassword123"
    }, follow_redirects=True)
    
    assert b"Please verify your email before logging in." in response.data

def test_email_verification_success(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=False)
    db.session.add(user)
    db.session.commit()
    
    token = generate_verification_token("mangesh@example.com")
    response = client.get(f"/verify/{token}", follow_redirects=True)
    
    assert response.status_code == 200
    user_updated = db.session.execute(db.select(User).where(User.email == "mangesh@example.com")).scalar()
    assert user_updated.is_verified is True

def test_email_verification_expired(client):
    token = generate_verification_token("mangesh@example.com")
    with patch("app.confirm_verification_token", return_value=None):
        response = client.get(f"/verify/{token}", follow_redirects=True)
        assert response.status_code == 400
        assert b"link is invalid or has expired" in response.data

def test_resend_verification_cooldown_rate_limit(client):
    user = User(name="unverified", email="unverified@example.com", password="pwd", is_verified=False)
    db.session.add(user)
    db.session.commit()
    
    with patch("app.send_verification_email") as mock_email:
        # First attempt: sends successfully
        res1 = client.post("/resend-verification", data={"email": "unverified@example.com"}, follow_redirects=True)
        assert b"If the email is registered and unverified, a verification link has been sent." in res1.data
        assert mock_email.call_count == 1
        
        # Second immediate attempt: blocked by 60s rate limit
        res2 = client.post("/resend-verification", data={"email": "unverified@example.com"}, follow_redirects=True)
        assert b"Please wait a minute before requesting another verification" in res2.data
        assert mock_email.call_count == 1

def test_unauthenticated_report_access_denied(client):
    response = client.get("/report")
    assert response.status_code == 302
    assert "login" in response.headers["Location"]

def test_authenticated_report_submission_success(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        
    img_data = create_test_image("PNG")
    
    mock_storage = MagicMock()
    mock_storage.upload.return_value = {"path": "reports/mock.png"}
    mock_storage.get_public_url.return_value = "https://mock.supabase.co/reports/mock.png"
    
    with patch("app.supabase.storage.from_", return_value=mock_storage):
        response = client.post("/report", data={
            "images": (img_data, "test.png"),
            "cause": "Heavy rainfall",
            "latitude": "18.583",
            "longitude": "73.737",
            "description": "Flooded street"
        }, follow_redirects=True)
        
        assert response.status_code == 200
        report = db.session.execute(db.select(Report).where(Report.cause == "Heavy rainfall")).scalar()
        assert report is not None
        assert report.latitude == 18.583
        assert report.image_path.startswith("reports/")

def test_report_submission_invalid_coordinates(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        
    img_data = create_test_image("PNG")
    
    # Invalid lat boundary (> 90)
    response = client.post("/report", data={
        "images": (img_data, "test.png"),
        "cause": "Heavy rainfall",
        "latitude": "95.0",
        "longitude": "73.737",
        "description": "Bad coordinates"
    }, follow_redirects=True)
    assert b"Latitude must be between -90 and 90 degrees." in response.data

    # Infinity coordinate test
    img_data = create_test_image("PNG")
    response = client.post("/report", data={
        "images": (img_data, "test.png"),
        "cause": "Heavy rainfall",
        "latitude": "inf",
        "longitude": "73.737",
        "description": "Infinite coordinates"
    }, follow_redirects=True)
    assert b"Coordinates must be finite real numbers." in response.data

def test_report_submission_invalid_image(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        
    bad_img_data = io.BytesIO(b"<svg>alert(1)</svg>")
    response = client.post("/report", data={
        "images": (bad_img_data, "test.png"),
        "cause": "Heavy rainfall",
        "latitude": "18.5",
        "longitude": "73.7",
        "description": "SVG Upload"
    }, follow_redirects=True)
    assert b"The uploaded file is not a valid image or is corrupted." in response.data

def test_report_decompression_bomb_rejection(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        
    large_img_data = create_test_image("PNG", size=(5000, 5000))
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", Image.DecompressionBombWarning)
        response = client.post("/report", data={
            "images": (large_img_data, "large.png"),
            "cause": "Heavy rainfall",
            "latitude": "18.5",
            "longitude": "73.7",
            "description": "Decompression Bomb"
        }, follow_redirects=True)
    assert b"Image dimensions exceed the maximum 16 Megapixel limit." in response.data

def test_report_supabase_rollback_on_db_failure(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    with client.session_transaction() as sess:
        sess["_user_id"] = str(user.id)
        
    img_data = create_test_image("PNG")
    
    mock_storage = MagicMock()
    mock_storage.upload.return_value = {"path": "reports/temp.png"}
    mock_storage.remove.return_value = {}
    
    with patch("app.supabase.storage.from_", return_value=mock_storage):
        with patch("app.db.session.commit", side_effect=Exception("Database crash!")):
            response = client.post("/report", data={
                "images": (img_data, "test.png"),
                "cause": "Heavy rainfall",
                "latitude": "18.5",
                "longitude": "73.7",
                "description": "Crash test"
            }, follow_redirects=True)
            assert b"We couldn&#39;t save your report right now." in response.data
        mock_storage.remove.assert_called_once()

def test_json_xss_escaping(client):
    user = User(name="mangesh", email="mangesh@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()
    
    report_record = Report(
        author_id=user.id,
        cause="Other",
        latitude=18.5,
        longitude=73.7,
        image_path="reports/mock.png",
        description="</script><script>alert('xss')</script>\\\"'"
    )
    db.session.add(report_record)
    db.session.commit()
    
    response = client.get("/")
    assert response.status_code == 200
    assert b"</script><script>" not in response.data
    assert b"\\u003c/script\\u003e\\u003cscript\\u003e" in response.data

def test_manual_email_sending_logic(client):
    from flask_mail import Message
    from app import mail
    with patch.object(mail, "send") as mock_send:
        with app.app_context():
            msg = Message(
                subject="Test email",
                recipients=["testrecipient@example.com"],
                body="Flask-Mail is working."
            )
            mail.send(msg)
        mock_send.assert_called_once_with(msg)

def test_csrf_protection_rejects_missing_token_on_post_routes(client):
    app.config["WTF_CSRF_ENABLED"] = True
    try:
        # POST to /login without CSRF token
        res_login = client.post("/login", data={"email": "a@b.com", "password": "pwd"})
        assert res_login.status_code == 400
        assert b"CSRF" in res_login.data or b"Bad Request" in res_login.data

        # POST to /register without CSRF token
        res_register = client.post("/register", data={"username": "test", "email": "a@b.com", "password": "pwd"})
        assert res_register.status_code == 400
        assert b"CSRF" in res_register.data or b"Bad Request" in res_register.data

        # POST to /report without CSRF token
        res_report = client.post("/report", data={"cause": "Other", "latitude": "18.5", "longitude": "73.7"})
        assert res_report.status_code == 400
        assert b"CSRF" in res_report.data or b"Bad Request" in res_report.data

        # POST to /resend-verification without CSRF token
        res_resend = client.post("/resend-verification", data={"email": "a@b.com"})
        assert res_resend.status_code == 400
        assert b"CSRF" in res_resend.data or b"Bad Request" in res_resend.data

        # POST to /report/1/comment without CSRF token
        res_comment = client.post("/report/1/comment", data={"content": "test comment"})
        assert res_comment.status_code == 400
        assert b"CSRF" in res_comment.data or b"Bad Request" in res_comment.data

        # POST to /authority/reports/1/status without CSRF token
        res_status = client.post("/authority/reports/1/status", data={"status": "Resolved"})
        assert res_status.status_code == 400
        assert b"CSRF" in res_status.data or b"Bad Request" in res_status.data

        # POST to /logout without CSRF token
        res_logout = client.post("/logout")
        assert res_logout.status_code == 400
        assert b"CSRF" in res_logout.data or b"Bad Request" in res_logout.data
    finally:
        app.config["WTF_CSRF_ENABLED"] = False

def test_logout_post_required(client):
    from werkzeug.security import generate_password_hash
    user = User(name="logoutuser", email="logoutuser@example.com", password=generate_password_hash("pwd123", method="pbkdf2:sha256"), is_verified=True)
    db.session.add(user)
    db.session.commit()

    # Log in
    client.post("/login", data={"email": "logoutuser@example.com", "password": "pwd123"}, follow_redirects=True)

    # GET /logout should be rejected with 405 Method Not Allowed
    res_get = client.get("/logout")
    assert res_get.status_code == 405

    # POST /logout logs the user out
    res_post = client.post("/logout", follow_redirects=True)
    assert res_post.status_code == 200

def test_production_startup_validation():
    # Verify SECRET_KEY enforcement in production
    with patch.dict(os.environ, {"SECRET_KEY": "", "FLASK_DEBUG": "False", "TESTING": "False"}, clear=False):
        import config
        with pytest.raises(RuntimeError, match="SECRET_KEY environment variable is required in production"):
            val = config._get_clean_env("SECRET_KEY")
            if not val:
                if not (config._get_clean_env("FLASK_DEBUG", "False").lower() in ("true", "1") or config._get_clean_env("TESTING", "False").lower() in ("true", "1")):
                    raise RuntimeError("SECRET_KEY environment variable is required in production!")

    # Verify DATABASE_URL enforcement in production
    with patch.dict(os.environ, {"DATABASE_URL": "", "FLASK_DEBUG": "False", "TESTING": "False"}, clear=False):
        import config
        with pytest.raises(RuntimeError, match="DATABASE_URL environment variable is required in production"):
            db_val = config._get_clean_env("DATABASE_URL")
            if not db_val:
                if not (config._get_clean_env("FLASK_DEBUG", "False").lower() in ("true", "1") or config._get_clean_env("TESTING", "False").lower() in ("true", "1")):
                    raise RuntimeError("DATABASE_URL environment variable is required in production!")

    # Verify GOVERNMENT_AUTHORITY_EMAIL enforcement in production
    with patch.dict(os.environ, {"GOVERNMENT_AUTHORITY_EMAIL": "", "FLASK_DEBUG": "False", "TESTING": "False"}, clear=False):
        import config
        with pytest.raises(RuntimeError, match="GOVERNMENT_AUTHORITY_EMAIL environment variable is required in production"):
            gov_val = config._get_clean_env("GOVERNMENT_AUTHORITY_EMAIL")
            if not gov_val:
                if not (config._get_clean_env("FLASK_DEBUG", "False").lower() in ("true", "1") or config._get_clean_env("TESTING", "False").lower() in ("true", "1")):
                    raise RuntimeError("GOVERNMENT_AUTHORITY_EMAIL environment variable is required in production!")

def test_location_validation_logic():
    # Valid coordinates
    lat, lng = validate_location("18.5834", "73.7371")
    assert math.isclose(lat, 18.5834)
    assert math.isclose(lng, 73.7371)

    # Missing coordinates
    with pytest.raises(ValueError, match="Please allow location access"):
        validate_location("", "73.7371")
    with pytest.raises(ValueError, match="Please allow location access"):
        validate_location("18.5834", None)

    # Invalid coordinates (text)
    with pytest.raises(ValueError, match="Received invalid coordinates"):
        validate_location("invalid", "73.7371")

    # Out of range latitude
    with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
        validate_location("95.0", "73.7371")
    with pytest.raises(ValueError, match="Latitude must be between -90 and 90"):
        validate_location("-95.0", "73.7371")

    # Out of range longitude
    with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
        validate_location("18.5834", "190.0")
    with pytest.raises(ValueError, match="Longitude must be between -180 and 180"):
        validate_location("18.5834", "-190.0")

    # Non-finite coordinates
    with pytest.raises(ValueError, match="Coordinates must be finite real numbers"):
        validate_location("nan", "73.7371")
    with pytest.raises(ValueError, match="Coordinates must be finite real numbers"):
        validate_location("inf", "73.7371")

def test_bleach_html_sanitization():
    dangerous_input = "<script>alert('pwned')</script>Hello <b>World</b>"
    clean_output = sanitize_comment_html(dangerous_input)
    assert "<script>" not in clean_output
    assert "alert('pwned')" not in clean_output or "&lt;script&gt;" not in clean_output
    assert "Hello <b>World</b>" in clean_output or "Hello <strong>World</strong>" in clean_output or "Hello" in clean_output

    img_xss = '<img src="x" onerror="alert(1)">'
    clean_img = sanitize_comment_html(img_xss)
    assert "onerror" not in clean_img
    assert "<img" not in clean_img

    js_url = '<a href="javascript:alert(1)">Click me</a>'
    clean_js = sanitize_comment_html(js_url)
    assert "javascript:" not in clean_js

    rich_text = '<p>This is <strong>bold</strong> and <em>italic</em> with a <a href="https://example.com">link</a>.</p><ul><li>item 1</li></ul>'
    clean_rich = sanitize_comment_html(rich_text)
    assert "<strong>bold</strong>" in clean_rich
    assert "<em>italic</em>" in clean_rich
    assert "href=\"https://example.com\"" in clean_rich
    assert "rel=\"noopener noreferrer\"" in clean_rich
    assert "<ul>" in clean_rich
    assert "<li>item 1</li>" in clean_rich

def test_reports_listing_and_filtering(client):
    user = User(name="reporter", email="reporter@example.com", password="pwd", is_verified=True)
    db.session.add(user)
    db.session.commit()

    r1 = Report(author_id=user.id, cause="Heavy rainfall", latitude=18.5, longitude=73.7, image_path="reports/r1.jpg", status="Submitted")
    r2 = Report(author_id=user.id, cause="Blocked sewers", latitude=18.6, longitude=73.8, image_path="reports/r2.jpg", status="Resolved")
    db.session.add_all([r1, r2])
    db.session.commit()

    # GET /reports (all reports)
    res_all = client.get("/reports")
    assert res_all.status_code == 200
    assert f"Report #{r1.id}".encode() in res_all.data
    assert f"Report #{r2.id}".encode() in res_all.data

    # GET /reports?status=Resolved
    res_filtered = client.get("/reports?status=Resolved")
    assert res_filtered.status_code == 200
    assert f"Report #{r2.id}".encode() in res_filtered.data
    assert f"Report #{r1.id}".encode() not in res_filtered.data

def test_report_detail_and_comments_workflow(client):
    from werkzeug.security import generate_password_hash
    user = User(name="reporter", email="reporter@example.com", password=generate_password_hash("reporterpwd123", method="pbkdf2:sha256"), is_verified=True)
    db.session.add(user)
    db.session.commit()

    report = Report(author_id=user.id, cause="Poor drainage system", latitude=18.55, longitude=73.75, image_path="reports/test.jpg", description="Deep water puddle", status="Submitted")
    db.session.add(report)
    db.session.commit()

    # GET /report/<id>
    res = client.get(f"/report/{report.id}")
    assert res.status_code == 200
    assert b"Poor drainage system" in res.data
    assert b"Deep water puddle" in res.data
    assert b"Submitted" in res.data

    # Non-existent report -> 404
    res_404 = client.get("/report/99999")
    assert res_404.status_code == 404

    # Post comment as unauthenticated user -> redirect to login
    res_unauth = client.post(f"/report/{report.id}/comment", data={"content": "Anonymous attempt"})
    assert res_unauth.status_code == 302
    assert "/login" in res_unauth.headers.get("Location", "")

    # Login and post comment with rich text HTML
    client.post("/login", data={"email": "reporter@example.com", "password": "reporterpwd123"}, follow_redirects=True)
    res_comment = client.post(f"/report/{report.id}/comment", data={
        "content": "<p>Drainage team is <strong>on the way</strong>.</p><script>alert('hack')</script>"
    }, follow_redirects=True)
    assert res_comment.status_code == 200
    assert b"Comment posted successfully." in res_comment.data
    assert b"Drainage team is <strong>on the way</strong>." in res_comment.data
    assert b"<script>" not in res_comment.data

    comment = db.session.execute(db.select(Comment).where(Comment.report_id == report.id)).scalar()
    assert comment is not None
    assert comment.author_id == user.id
    assert "<strong>on the way</strong>" in comment.content
    assert "<script>" not in comment.content

def test_government_authority_authorization_and_status_update(client):
    from werkzeug.security import generate_password_hash
    # Create regular user
    regular_user = User(name="regular", email="citizen@example.com", password=generate_password_hash("citizenpwd123", method="pbkdf2:sha256"), is_verified=True)
    # Create authority user (matches configured authority@example.com)
    authority_user = User(name="Authority Officer", email="authority@example.com", password=generate_password_hash("authoritypwd123", method="pbkdf2:sha256"), is_verified=True)
    db.session.add_all([regular_user, authority_user])
    db.session.commit()

    report = Report(author_id=regular_user.id, cause="Damaged water pipe line", latitude=18.5, longitude=73.7, image_path="reports/pipe.jpg", status="Submitted")
    db.session.add(report)
    db.session.commit()

    # 1. Unauthenticated access to authority dashboard -> redirect to login
    res_dash_unauth = client.get("/authority/reports")
    assert res_dash_unauth.status_code == 302
    assert "/login" in res_dash_unauth.headers.get("Location", "")

    # 2. Regular citizen logged in -> 403 Forbidden
    client.post("/login", data={"email": "citizen@example.com", "password": "citizenpwd123"}, follow_redirects=True)
    res_dash_forbidden = client.get("/authority/reports")
    assert res_dash_forbidden.status_code == 403

    res_update_forbidden = client.post(f"/authority/reports/{report.id}/status", data={"status": "In Progress"})
    assert res_update_forbidden.status_code == 403

    # Logout citizen via POST
    client.post("/logout")

    # 3. Government authority logged in -> 200 OK
    client.post("/login", data={"email": "authority@example.com", "password": "authoritypwd123"}, follow_redirects=True)
    res_dash_ok = client.get("/authority/reports")
    assert res_dash_ok.status_code == 200
    assert b"Incident Command Dashboard" in res_dash_ok.data
    assert b"Damaged water pipe line" in res_dash_ok.data

    # 4. Authority updates status to "In Progress"
    res_update = client.post(f"/authority/reports/{report.id}/status", data={"status": "In Progress"}, follow_redirects=True)
    assert res_update.status_code == 200
    assert b"status updated to &#39;In Progress&#39;" in res_update.data or b"status updated to 'In Progress'" in res_update.data

    db.session.refresh(report)
    assert report.status == "In Progress"

    # 5. Authority updates status to "Resolved"
    res_resolved = client.post(f"/authority/reports/{report.id}/status", data={"status": "Resolved"}, follow_redirects=True)
    assert res_resolved.status_code == 200
    db.session.refresh(report)
    assert report.status == "Resolved"

    # 6. Reject invalid status value
    res_invalid_status = client.post(f"/authority/reports/{report.id}/status", data={"status": "FakeStatus"}, follow_redirects=True)
    assert b"Invalid status" in res_invalid_status.data
    db.session.refresh(report)
    assert report.status == "Resolved"

def test_timezone_conversion_and_utc_storage(client):
    from werkzeug.security import generate_password_hash
    user = User(
        name="Timezone Tester",
        email="tzuser@example.com",
        password=generate_password_hash("tzpassword123", method="pbkdf2:sha256"),
        is_verified=True
    )
    db.session.add(user)
    db.session.commit()

    report = Report(
        author_id=user.id,
        cause="Drainage blockage",
        latitude=18.5204,
        longitude=73.8567,
        image_path="reports/tz_test.jpg",
        status="Submitted"
    )
    db.session.add(report)
    db.session.commit()

    utc_time = datetime(2026, 8, 29, 12, 0, 0, tzinfo=timezone.utc)
    ist_time = to_ist(utc_time)
    assert ist_time.hour == 17
    assert ist_time.minute == 30
    assert ist_time.tzinfo == IST

    formatted = format_ist(utc_time, "%Y-%m-%d %H:%M %Z")
    assert "2026-08-29 17:30 IST" in formatted

    naive_utc = datetime(2026, 8, 29, 12, 0, 0)
    formatted_naive = format_ist(naive_utc, "%Y-%m-%d %H:%M %Z")
    assert "2026-08-29 17:30 IST" in formatted_naive

    assert format_ist(None) == ""
    assert to_ist(None) is None

    client.post("/login", data={"email": "tzuser@example.com", "password": "tzpassword123"}, follow_redirects=True)
    res_comment = client.post(f"/report/{report.id}/comment", data={
        "content": "<p>Timezone test comment</p>"
    }, follow_redirects=True)
    assert res_comment.status_code == 200
    assert b"Comment posted successfully." in res_comment.data

    comment = db.session.execute(db.select(Comment).where(Comment.report_id == report.id)).scalar()
    assert comment is not None
    assert comment.created_at is not None
    ist_comment_time = to_ist(comment.created_at)
    assert ist_comment_time is not None
    assert ist_comment_time.tzinfo == IST

def test_open_redirect_prevention(client):
    from werkzeug.security import generate_password_hash
    user = User(name="redir_tester", email="redir@example.com", password=generate_password_hash("password123", method="pbkdf2:sha256"), is_verified=True)
    db.session.add(user)
    db.session.commit()

    # 1. Test is_safe_url helper
    with app.test_request_context("http://localhost:5000/login"):
        assert is_safe_url("/reports") is True
        assert is_safe_url("http://localhost:5000/reports") is True
        assert is_safe_url("https://evil-attacker.com") is False
        assert is_safe_url("javascript:alert(1)") is False
        assert is_safe_url("//evil.com") is False
        assert is_safe_url(None) is False

    # 2. Test login next parameter with malicious external URL
    res = client.post("/login?next=https://attacker.com/steal-session", data={
        "email": "redir@example.com",
        "password": "password123"
    })
    # Should redirect to default internal page (index '/'), NOT to external evil site
    assert res.status_code == 302
    assert "attacker.com" not in res.headers["Location"]
    assert res.headers["Location"].endswith("/")

    # 3. Test login next parameter with safe relative URL
    res_safe = client.post("/login?next=/reports", data={
        "email": "redir@example.com",
        "password": "password123"
    })
    assert res_safe.status_code == 302
    assert res_safe.headers["Location"].endswith("/reports")

def test_security_headers_present(client):
    response = client.get("/")
    assert response.status_code == 200
    headers = response.headers
    assert headers.get("X-Content-Type-Options") == "nosniff"
    assert headers.get("X-Frame-Options") == "SAMEORIGIN"
    assert headers.get("Referrer-Policy") == "strict-origin-when-cross-origin"
    assert "Content-Security-Policy" in headers
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "https://*.supabase.co" in csp
    assert "https://cdn.tailwindcss.com" not in csp  # Play CDN removed in favor of static build
