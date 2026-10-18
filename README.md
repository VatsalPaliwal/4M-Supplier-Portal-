# 4M Change Management – Supplier Portal

A web portal that lets manufacturing suppliers submit their monthly 4M change declarations, and lets quality administrators review, track and export them. It replaces ad-hoc spreadsheet and email exchanges with a single, structured and authenticated workflow.

> **Status:** working prototype, built to demonstrate the workflow to an IT department ahead of a possible full deployment. Not production-hardened (see [Limitations](#limitations-and-roadmap)).

## Background

In manufacturing quality management, a supplier must report any change to the **4Ms** that could affect product quality:

| Category | Meaning |
|----------|---------|
| Man | People, operators, training |
| Machine | Equipment, tooling |
| Method | Processes, procedures |
| Material | Inputs, components |

Each supplier files one submission per month. This portal collects those submissions in one place, enforces one submission per supplier per month, and gives administrators a dashboard and Excel export.

## Features

**Suppliers**
- Log in with their own credentials
- Upload a monthly 4M change submission with supporting documents
- View their submission history

**Administrators**
- Log in with two-factor authentication (one-time password)
- Dashboard of submissions across suppliers
- Create and edit supplier accounts, and reset supplier passwords
- Export submissions to Excel

**Platform**
- Server-side session authentication with a custom session table
- Duplicate protection: one submission per supplier, per month, per year (database constraint)
- Content-type-aware error handling: JSON errors for `fetch()` calls, HTML error pages for browser requests

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | Python, FastAPI |
| Database / ORM | SQLite, SQLAlchemy |
| Templating | Jinja2 (server-rendered) |
| Frontend | HTML, CSS, Bootstrap 5, Bootstrap Icons, vanilla JavaScript |
| Auth | Custom cookie sessions, hashed passwords, OTP for admins |

## Architecture

The app is **server-rendered**: pages are Jinja2 templates, forms submit as plain HTML POSTs, and state is carried by a session cookie. It is not a JSON API, so routes set cookies explicitly and respond with redirects.

```
Browser ──form POST / GET──▶ FastAPI routes ──▶ SQLAlchemy ──▶ SQLite
   ▲                              │
   └──── Jinja2-rendered HTML ◀───┘
```

### Data model

| Table | Purpose |
|-------|---------|
| `Users` | Login accounts (suppliers and admins), with hashed passwords |
| `Suppliers` | Supplier records |
| `Submission` | One monthly submission per supplier |
| `ChangeDocs` | Documents attached to a submission |
| `UserSession` | Server-side sessions behind the login cookie |

`Submission` has a unique constraint on `(supplier_id, month, year)`, so a supplier cannot file twice for the same month.

### Authentication

- Passwords are stored as hashes and verified on login.
- Sessions live in the `UserSession` table (not Starlette's built-in session middleware), which allows explicit creation and destruction on login and logout.
- Admin logins require a second step: a one-time password.

## Pages

1. Login
2. Supplier upload (4M Change Control System)
3. Submission history
4. Admin dashboard
5. Admin utilities: create supplier, edit supplier, reset password

## Getting started

**Requirements:** Python 3.10+

```bash
# 1. Clone the repository and enter it
git clone <repository-url>
cd <project-folder>

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Start the development server
uvicorn main:app --reload
```

Then open `http://127.0.0.1:8000`. The SQLite database file is created on first run.

> Adjust `main:app` to match your entry-point module if it differs.

## Project structure

```
├── main.py            # FastAPI app and route registration
├── models.py          # SQLAlchemy models
├── auth.py            # Password hashing, sessions, current-user helpers
├── routes/            # Page and form handlers
├── templates/         # Jinja2 templates
├── static/            # CSS, JS, images
└── requirements.txt
```

> This layout is illustrative. Replace it with the actual file tree before publishing.

## Design decisions

- **Server-rendered over a JSON API.** For a small internal tool with a handful of forms, Jinja2 plus form POSTs avoids a separate frontend build and keeps authentication simple.
- **Custom session table.** Sessions are stored in the database and can be listed, expired or destroyed explicitly.
- **Constraint in the database, not only the code.** The monthly-uniqueness rule is enforced by a `UniqueConstraint`, so it holds even if application logic changes.
- **Content-negotiated errors.** The global exception handler checks the `Accept` header so JavaScript `fetch()` calls get JSON instead of an HTML error page.

## Limitations and roadmap

- SQLite is suitable for a prototype; a production deployment would move to a server database.
- Self-service password reset by email is deferred until a company email address is available. Admins currently reset passwords manually.
- Remaining work: finish backend route coverage and run end-to-end testing of all flows.
- Production hosting, HTTPS and secret management would be handled by the deploying IT team.

## Notes

This project was built as an internship project. Credentials, supplier data and company details are not included in the repository.
