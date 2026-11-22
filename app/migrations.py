"""Conservative schema bootstrapping. Never drop tables or erase rows.

Uses create_all() for brand-new installations and records schema version. For future
schema modifications, add a forward-only revision to ADDITIVE_MIGRATIONS; don't
edit the original table model and expect create_all() to alter existing tables.
"""
from sqlalchemy import text
from .extensions import db

# SQL statements for future forward-only alterations, keyed by increasing version.
ADDITIVE_MIGRATIONS = {}
CURRENT_SCHEMA_VERSION = 1


def upgrade_schema():
    db.create_all()  # create missing tables only; NEVER drops existing data
    with db.engine.begin() as conn:
        conn.execute(text('CREATE TABLE IF NOT EXISTS schema_versions '
                          '(version INTEGER PRIMARY KEY, applied_at DATETIME DEFAULT CURRENT_TIMESTAMP)'))
        versions = {row[0] for row in conn.execute(text('SELECT version FROM schema_versions'))}
        if not versions:
            conn.execute(text('INSERT INTO schema_versions(version) VALUES (1)'))
            versions.add(1)
        for version in sorted(ADDITIVE_MIGRATIONS):
            if version not in versions:
                for statement in ADDITIVE_MIGRATIONS[version]:
                    conn.execute(text(statement))
                conn.execute(text('INSERT INTO schema_versions(version) VALUES (:v)'), {'v': version})
