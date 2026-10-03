import logging
from flask_mail import Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from config import SECRET_KEY

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

s = URLSafeTimedSerializer(secret_key=SECRET_KEY)

def generate_verification_token(email):
    payload = {
        "email": email,
        "action": "email-verification"
    }
    return s.dumps(payload, salt='email-confirm')

def confirm_verification_token(token, expiration=3600):
    try:
        payload = s.loads(token, salt='email-confirm', max_age=expiration)
        if isinstance(payload, dict) and payload.get("action") == "email-verification":
            return payload.get("email")
        if isinstance(payload, str):
            return payload
        return None
    except (SignatureExpired, BadSignature):
        return None

def send_email(email, verify_url):
    from app import app, mail   # local import — avoids circular import with app.py

    sender = app.config.get("MAIL_DEFAULT_SENDER") or app.config.get("MAIL_USERNAME")

    msg = Message(
        subject="Verify your Water Clogging Reporter Account",
        sender=sender,
        recipients=[email],
        body=f"Welcome to Water Clogging Reporter!\n\nPlease verify your account by clicking the following link:\n{verify_url}\n\nIf you did not sign up for this account, please ignore this email.",
        html=f"""
        <h2>Verify your Water Clogging Reporter Account</h2>
        <p>Welcome to Water Clogging Reporter!</p>
        <p>Please click the link below to verify your email address and activate your account:</p>
        <p><a href="{verify_url}" style="display: inline-block; padding: 10px 20px; color: white; background-color: #007bff; text-decoration: none; border-radius: 5px;">Verify Email Address</a></p>
        <p>If the button doesn't work, copy and paste the link below into your web browser:</p>
        <p><a href="{verify_url}">{verify_url}</a></p>
        <br>
        <p>If you did not sign up for this account, please ignore this email.</p>
        """
    )
    mail.send(msg)

def send_verification_email(email_to, verify_url):
    # Let exceptions propagate so the caller (app.py) can handle sending failure properly
    send_email(email=email_to, verify_url=verify_url)
    logging.info(f"Verification email sent to {email_to}.")