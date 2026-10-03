# Water Log Reporter - Production Deployment & Operations Guide

A community water clogging reporting and emergency management web application built with Flask, SQLAlchemy, Flask-Migrate, Flask-Login, Flask-WTF, and Supabase Storage.

---

## 1. Production Build & Deployment Commands

### Build Command

```bash
pip install -r requirements.txt
```

### Database Migration Command

```bash
flask db upgrade
```

### Production WSGI Start Command

```bash
gunicorn wsgi:app
```

_(Do not use `flask run` or `python app.py` as the production server)._

---

## 2. Environment Variables Specification

Create a `.env` file based on `.env.example` with the following parameters:

### Required Production Variables

- `SECRET_KEY`: Cryptographically strong secret key for signing sessions, CSRF tokens, and email verification tokens.
- `DATABASE_URL`: Production PostgreSQL database connection string (e.g. `postgresql://user:password@host:5432/dbname`).
- `SUPABASE_URL`: Supabase project URL (e.g. `https://your-project.supabase.co`).
- `SUPABASE_KEY`: Supabase service or anon API key with storage permissions.
- `MAIL_USERNAME`: SMTP server username (e.g. Gmail address).
- `MAIL_PASSWORD`: SMTP app password or credential.
- `MAIL_DEFAULT_SENDER`: From email address used on outbound transactional emails.
- `GOVERNMENT_AUTHORITY_EMAIL`: Normalized email address authorized for the Incident Command Dashboard and status changes.

### Configurable Mail Variables

- `MAIL_SERVER`: SMTP server host (defaults to `smtp.gmail.com`).
- `MAIL_PORT`: SMTP server port (defaults to `587`).
- `MAIL_USE_TLS`: Enable TLS (defaults to `True`).
- `MAIL_USE_SSL`: Enable SSL (defaults to `False`).

### Rate Limiting & Distributed Backend

- `RATELIMIT_STORAGE_URL`: Shared storage URI for multi-worker / multi-instance setups (e.g. `redis://localhost:6379/0`). If omitted, defaults to in-memory limiting with a production log warning.

### Production Security Flags (Default to Secure)

- `FLASK_DEBUG`: `False` (production must NEVER run with debug=True).
- `TESTING`: `False`.
- `SESSION_COOKIE_SECURE`: `True` (forces cookies over HTTPS).
- `REMEMBER_COOKIE_SECURE`: `True`.
- `ENABLE_HSTS`: `True` (Strict-Transport-Security header enabled).

---

## 3. Key Architecture & Hardening Features

- **Server-Side Upload Sanitization:** Re-encodes uploaded images with Pillow, rejecting SVGs, HTML disguised as images, corrupted files, and decompression bombs exceeding 16 megapixels.
- **XSS Defense:** Strict server-side HTML sanitization with Bleach on rich-text comments and DOM-based text node rendering in Leaflet map popups.
- **CSRF Protection:** Universal CSRF protection enforced across all state-changing endpoints, including POST-based logout.
- **Open Redirect Defense:** URL parsing validation preventing off-domain redirect manipulation.
- **Database Resiliency:** Transactional rollback and storage cleanup handlers on database errors; PostgreSQL connection pooling (`pool_pre_ping=True`, `pool_recycle=300`).
- **Static Asset Compilation:** Built-in compiled Tailwind CSS serving directly from `/static/css/tailwind.css` to enable tight Content Security Policy (CSP).

---

## 4. Running Tests

```bash
pytest
```

## 📸 Screenshots

<table>
  <tr>
    <td><b>Home Page</b></td>
    <td><b>Login Page</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/home.png" alt="Home Page"></td>
    <td><img src="docs/screenshots/login.png" alt="Login Page"></td>
  </tr>
  <tr>
    <td><b>Report Water Logging</b></td>
    <td><b>Water Clogged Locations Map</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/report.png" alt="Report Water Logging"></td>
    <td><img src="docs/screenshots/map.png" alt="Water Clogged Locations Map"></td>
  </tr>
</table>
