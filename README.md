# CampusFind AI — Group 9
## Intelligent Lost & Found Object Matching System

**Fully local academic Flask application** for student lost/found reporting, explainable AI-powered matching, protected ownership claims, and admin review. Written for **Windows 11, VS Code, PowerShell and Python 3.13**.

> This is a coursework-oriented prototype, not a production identity-verification system. AI similarity indicates candidate overlap, not legal proof of ownership.

## 1 — Quick start (Windows)

1. Download `Intelligent_Lost_Found_System.zip`, right-click **Extract All**, and open the extracted **Intelligent_Lost_Found_System** folder in VS Code (`File → Open Folder`).
2. Open **Terminal → New Terminal**, then run:

```powershell
.\run_windows.bat
```

The batch script creates `.venv` (if missing), installs dependencies and launches Flask. The first install may be slow because NumPy, OpenCV, and scikit-learn have substantial wheels.

3. Open **http://127.0.0.1:5000** in your browser. Keep the terminal open while using the website. Press `Ctrl+C` to stop.

### Manual setup in VS Code (exact commands)

```powershell
# Open the extracted folder in VS Code first
py -3.13 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python run.py
```

If PowerShell refuses to activate the venv, use this in the same PowerShell terminal:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

Alternatively, **activation is optional**:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe run.py
```

Never run the Streamlit script from the old Group 9 project: **this is a Flask app**, and the correct launch command is `python run.py`.

## 2 — Default administrator

New installations create one default **admin** account automatically:

| Field | Value |
|---|---|
| Email | `admin@campusfind.local` |
| Password | `CampusFind@2026!` |

**First login MUST change the default password** before the admin console becomes accessible. It is saved as a secure password hash (not plaintext). You may also reset it interactively from the terminal:

```powershell
python -m flask --app run change-admin-password
```

After reset, sign in with the same email and the new password. To change the default email/password **before a brand-new database is created**, copy `.env.example` to `.env` and set `ADMIN_EMAIL` and `ADMIN_PASSWORD` there. The env file does not change existing passwords automatically (this prevents accidental account resets). Do not put real passwords in Git.

For sample students, create accounts using the public registration form. Admin privileges cannot be self-assigned.

## 3 — Student workflow

1. Register a student account, then sign in.
2. Select **+ Report item** and choose **Lost** or **Found**.
3. Enter name, category, description, location, event date/time, contact information; attach an optional valid image (JPG/JPEG/PNG/WEBP, max 6 MB).
4. Submission is validated, saved, and **automatically approved** if it meets the checks. More than 8 reports within 1 hour triggers **Pending Review** to reduce abuse; admin may approve/reject such exceptions. Invalid submissions display errors and do not create records.
5. The AI calculates comparison scores immediately against every currently approved opposite-type report, saves real ranked candidates, and shows results in the student's dashboard. New reports also become searchable in **Explore items**.
6. On each **approved found** report, an eligible signed-in student (not the finder and not already a claimant) sees the **Claim This Item** button. This leads to a form with ownership details, distinguishing characteristics, optional linked lost report and optional private photo evidence.
7. Claim stages: **Submitted → Under Review → Approved or Rejected**. Students can track this on their dashboards.
8. **Only an admin-approved claim** causes a found item to become **Returned**. If the claim is linked to an approved lost report, that report becomes Returned too. Other pending claims against the returned found item are rejected.

The image upload is intentionally **optional** to accommodate text-only reports, which the original project brief permits. Text/category/location/date-time weights are automatically renormalized when an image is unavailable.

## 4 — AI matching implementation (all offline)

Two reports are compared only when one is Lost and the other Found. The model uses:

| Signal | Algorithm | Default weight |
|---|---|---:|
| Text | scikit-learn TF-IDF word unigrams/bigrams + cosine similarity | 35% |
| Image | OpenCV ORB descriptors + HSV colour histogram | 35% |
| Category | Exact category equality | 15% |
| Location | Normalized token overlap + fuzzy string ratio | 10% |
| Date/time | Exponentially decaying event date/time proximity | 5% |

Score: `sum(available_weight_i * similarity_i) / sum(available_weight_i)`.

- **Strong**: 80–100%
- **Possible**: 60–79.99%
- **Weak**: below 60%

The model is explainable and deterministic for a fixed dataset. Thresholds can be overridden in `.env`. Weights are defined in `config.py` and may be adjusted there. Different candidate corpora can slightly affect TF-IDF similarities, so matching is recomputed when a new comparison is added. OpenCV ORB is a local image feature technique; it is not a pretrained image object detector, and colour/angle variations can affect scores.

**Important:** Scores are NOT ownership verification and never automatically approve a claim.

## 5 — Optional demo data (synthetic reports)

The initial database starts with an administrator and **no fabricated campus incidents**. If you want realistic-looking example reports for a faculty demonstration:

```powershell
python -m scripts.seed_demo
```

This adds two clearly synthetic sample students and two paired example items. Their image and text similarity is computed with the **real** AI engine (no hardcoded scores). Demo users:

- `demo.alex@example.invalid` / `DemoStudent123`
- `demo.jamie@example.invalid` / `DemoStudent123`

Do not treat sample data as actual student information. Running the command again is idempotent.

## 6 — Data storage, backups and safe upgrades

- Main SQLite file: `instance/campusfind.db`
- Report images: `instance/uploads/items/`
- Claim evidence: `instance/uploads/claims/`
- Local cookie secret: `instance/.local-secret` (if no `SECRET_KEY` in `.env`)

These paths are generated automatically and excluded by `.gitignore`. The application invokes **`db.create_all()`** to create missing tables and keeps schema-version metadata. No startup code executes `drop_all()` or deletes existing records. **Existing tables are never overwritten.**

Before modifying the schema or applying updates, make a database backup:

```powershell
python -m scripts.backup_database
```

It creates a timestamped backup in `backups/`. Source records remain intact. For **future schema changes**, add an explicit forward-only SQL revision to `app/migrations.py` (`ADDITIVE_MIGRATIONS`) after backing up; `create_all()` **does not** automatically add new columns to existing tables. This project ships schema version 1 and is migration-ready for future controlled revisions. An older Streamlit SQLite file has a different schema and **cannot simply be renamed** to this Flask database; a separate importer would be needed.

## 7 — Security and roles

- Passwords are hashed via Werkzeug.
- Login uses Flask-Login and secure same-site HTTP-only session cookies.
- Every POST form uses Flask-WTF CSRF tokens.
- Role checks protect student actions and admin operations.
- User email, item contact details and claimant evidence are not shown to other students.
- Images are checked for real format, dimensions and size, then re-encoded into clean JPEG with random filenames.
- Duplicate reports (same user, type and normalized details) and duplicate claims (same student/found item) are blocked by database uniqueness constraints.
- Rate-limited suspicious reports get a **Pending Review** status; normal reports are auto-approved.
- Only an admin decision can return an item. Claim approval is separate from report approval.
- Input is validated on the server and rendered with auto-escaping HTML templates.

On localhost, HTTPS is not configured and `SESSION_COOKIE_SECURE` is intentionally not set; don't expose the development server to the public Internet. Add TLS, audit logging, recovery policies and production rate limiting before using with real student data.

## 8 — Run tests

```powershell
python -m pip install -r requirements-dev.txt
python -m pytest -q
```

Tests cover registration/login, lost/found reports, auto-approval, matching percentages, claim button visibility, claims, under-review, admin approval/rejection, Returned rules, duplicate reports/claims, invalid image rejection, privacy, admin authorization, CSRF, database persistence, and offline image/text scoring.

**Test verification note:** In the authoring environment, Python 3.13, NumPy, OpenCV, scikit-learn, Jinja2 and pytest were available, but Flask and other Flask extensions could not be installed because the package network was unavailable. Therefore the isolated AI tests and static Python/Jinja checks were executed, while the Flask end-to-end tests and live server startup must be executed on Windows after `pip install`. Do not assume the full browser workflows were already tested.

## 9 — Folder structure

```text
Intelligent_Lost_Found_System/
├── app/
│   ├── __init__.py          Flask application factory
│   ├── auth.py              Register, login, profile, password change
│   ├── routes.py            Home, search, details, private image endpoints
│   ├── student.py           Report, dashboard, matches, claim form
│   ├── admin.py             Claims review, moderation and statistics
│   ├── matching.py          Scoring persistence
│   ├── models.py            User, Item, Match and Claim relationships
│   ├── migrations.py        Safe bootstrap and version metadata
│   ├── extensions.py        Flask database/login/CSRF integrations
│   ├── utils.py             Validation, image sanitation, role checks
│   ├── templates/           20 complete Jinja HTML templates
│   └── static/
│       ├── css/style.css
│       ├── js/app.js
│       └── vendor/          Bundled Bootstrap 5 CSS + JS
├── ai_engine/
│   ├── text_matching.py
│   ├── image_matching.py
│   └── matching_engine.py
├── scripts/                Optional seed and SQLite backup
├── tests/                  AI unit tests + Flask integration tests
├── instance/               Runtime database and image files (ignored)
├── config.py
├── run.py
├── run_windows.bat
├── requirements.txt
├── requirements-dev.txt
├── QUICK_START.txt
└── README.md
```

## Troubleshooting

- **`No module named flask`**: activate `.venv` or run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt`.
- **`py -3.13` not found**: install Python 3.13 from python.org, check **Add Python to PATH**, then reopen VS Code.
- **PowerShell does not allow activation**: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`, or use the `.venv` Python directly.
- **Port 5000 occupied**: stop the other Flask server with Ctrl+C. You can also edit `port=5000` in `run.py` for local testing.
- **Old UI still showing**: make sure you opened this *Flask* folder, not the previous Streamlit folder; browser URL must be `127.0.0.1:5000`, not `localhost:8501`.
- **Slow on first run**: most of the wait is downloading compiled scientific Python packages; future runs can use `python run.py` directly.
- **Admin login redirected**: this is by design; the initial admin password MUST be rotated first.
- **No candidate matches**: there must be at least one approved report of each type. You can optionally seed demo data for presentation.
