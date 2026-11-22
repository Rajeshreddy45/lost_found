# Feature Implementation & Verification Checklist

## What is implemented

| Requirement | Implemented? | Flask integration test written? | Executed in authoring environment? |
|---|---|---|---|
| Student registration / login / logout / profile | Yes | Yes | No — Flask unavailable |
| Admin account, RBAC, forced password reset | Yes | Yes | No — Flask unavailable |
| Lost report submission | Yes | Yes | No — Flask unavailable |
| Found report submission | Yes | Yes | No — Flask unavailable |
| Auto-approval valid reports and exceptional Pending Review | Yes | Yes | No — Flask unavailable |
| Immediate TF-IDF + OpenCV AI ranking | Yes | Yes | **Core engine tests passed; Flask integration not run** |
| Show actual match percentage / explanations | Yes | Yes | Template parsed, not rendered live |
| Visible Claim This Item button | Yes | Yes | Template parsed, not rendered live |
| Ownership claim with private photo evidence | Yes | Yes | No — Flask unavailable |
| Claim Submitted / Under Review / Approved / Rejected | Yes | Yes | No — Flask unavailable |
| Return only following approved claim | Yes | Yes | No — Flask unavailable |
| Duplicate claims and reports | Yes | Yes | No — Flask unavailable |
| Admin students/reports/matches/claims and decisions | Yes | Yes | No — Flask unavailable |
| CSRF, server validation, uploads and private contact data | Yes | Yes | No — Flask unavailable |
| SQLite non-destructive bootstrapping, backup script | Yes | Yes | No — Flask unavailable |
| Bootstrap 5 mobile-responsive HTML/CSS/JS | Yes | Structural checks | Visual browser testing not available |

## Tests actually executed

1. `python -m compileall -q` — all Python source files compile successfully.
2. Jinja2 loader parsed **20 HTML templates** successfully.
3. Static route/link audit found **0 undefined url_for endpoints**.
4. `pytest -q --noconftest tests/test_engine.py` — **6 passed**, including TF-IDF, missing-image weight redistribution, configurable levels, location/time proximity, genuine local OpenCV image comparisons, and ranking.

## Tests NOT executed

`pytest -q tests/test_flask_workflows.py` and live Flask startup/browser verification require Flask + Flask-Login + Flask-SQLAlchemy + Flask-WTF, which were unavailable and could not be installed in the authoring environment (package network blocked). These **14 Flask workflow tests** are included to run on Windows after the dependencies are installed. Do not assume they passed until they actually run.

## Running final verification on Windows

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe run.py
```

Then check the UI in your browser at `http://127.0.0.1:5000`, because a static template compilation cannot prove how a page looks or behaves interactively.
