# TalentHub 💼

A **reverse job platform** built with Flask. Instead of companies posting jobs,
**candidates create a profile once** (skills, experience, cover letter, CV),
and **employers browse, filter, and shortlist** to find the right person.

This started as a small demo project and grew into a full, launch-ready web
app with accounts, roles, and real security - built as a way to practise
production-grade full-stack development (with AI-assisted coding along the way).

## ✨ Features

**For candidates**
- Sign up, create one profile (skills, role, location, experience level, cover letter)
- Upload a CV (PDF only - the file's actual content is checked, not just the extension)
- Dashboard showing profile views and how many times you've been shortlisted
- Edit or delete your profile anytime

**For employers**
- Browse all candidates with pagination
- Filter by skill, role, location, and experience level
- View full profiles and download CVs
- Shortlist candidates and manage them from a dedicated dashboard

**Under the hood**
- Password hashing (no plain-text passwords, ever)
- CSRF protection on every form
- Rate limiting on login/signup to slow down brute-force attempts
- Role-based access control (candidates and employers can't reach each other's pages)
- Secure session cookies
- Custom 404 / 403 / 500 error pages
- Automated test suite (pytest)

## 🛠️ Built With

- **Python** + **Flask** (application factory + blueprints)
- **Flask-SQLAlchemy** + **Flask-Migrate** (database + migrations)
- **Flask-Login** (sessions/authentication)
- **Flask-WTF** (forms + CSRF protection)
- **Flask-Limiter** (rate limiting)
- **SQLite** locally, **PostgreSQL** in production
- **gunicorn** (production WSGI server)
- Custom HTML/CSS with inline SVG icons - no frontend framework

## 📂 Project Structure

```
jobplatform/
├── run.py                  # entry point (python run.py, or gunicorn run:app)
├── config.py               # Dev / Production / Testing configs
├── requirements.txt
├── .env.example             # copy to .env and fill in for local dev
├── Procfile                 # for gunicorn on Render/Heroku-style platforms
├── render.yaml               # Render deploy config (web service + Postgres)
├── app/
│   ├── __init__.py          # create_app() application factory
│   ├── extensions.py        # db, migrate, login_manager, csrf, limiter
│   ├── models.py             # User, CandidateProfile, Shortlist, ProfileView
│   ├── forms.py               # WTForms (signup, login, profile)
│   ├── utils.py                # role_required decorator, real PDF validation
│   ├── auth/                    # signup / login / logout
│   ├── candidates/               # profile create / edit / dashboard
│   ├── employer/                  # browse / filter / shortlist / CV download
│   ├── main/                       # landing page + error handlers
│   ├── templates/                   # all HTML (Jinja2)
│   └── static/css/style.css          # all styling
├── uploads/                 # uploaded CVs (gitignored, folder tracked)
└── tests/                    # pytest suite (auth, profiles, employer flows)
```

## 🚀 Running Locally

1. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   venv\Scripts\activate      # Windows
   source venv/bin/activate   # Mac/Linux
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Copy the example environment file and set a real secret key:
   ```bash
   copy .env.example .env      # Windows
   cp .env.example .env        # Mac/Linux
   ```
   Generate a secret key with:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
4. Run the app:
   ```bash
   python run.py
   ```
5. Open **http://127.0.0.1:5000**

The SQLite database is created automatically the first time you run it.

## 🧪 Running Tests

```bash
python -m pytest tests/ -v
```

## ☁️ Deploying (Render)

1. Push this repo to GitHub.
2. Create a new **Blueprint** on [Render](https://render.com) and point it at this repo -
   it will read `render.yaml` and automatically set up:
   - A web service running `gunicorn run:app`
   - A managed PostgreSQL database, wired up via the `DATABASE_URL` env var
   - A generated `SECRET_KEY`
3. Once deployed, Render runs the app with `FLASK_ENV=production`, which enables
   secure cookies and connects to PostgreSQL instead of SQLite.

### Database migrations in production
```bash
flask db init      # only once, to create the migrations folder
flask db migrate -m "Initial migration"
flask db upgrade
```

## 🔒 Security Notes

- Passwords are hashed with Werkzeug's `generate_password_hash` - never stored in plain text.
- Every form is protected against CSRF via Flask-WTF.
- Login and signup are rate-limited to slow down brute-force attempts.
- Uploaded CVs are checked for real PDF content (not just a `.pdf` extension) and capped at 5 MB.
- Candidates can only edit or delete their own profile; only employers (or the
  profile owner) can download a CV.
- Session cookies are `HttpOnly`, `SameSite=Lax`, and marked `Secure` in production.

## 📬 Contact

Built by **Shazad Arshad** (with AI-assisted coding) - part of a personal portfolio.

---

⭐ If you find this useful, feel free to star the repo!
