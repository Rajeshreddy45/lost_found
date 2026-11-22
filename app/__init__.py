"""Flask application factory."""
import secrets
from pathlib import Path

import click
from flask import Flask, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user
from sqlalchemy import event
from sqlalchemy.engine import Engine

from config import BASE_DIR, Config
from .extensions import csrf, db, login_manager
from .models import User
from .migrations import upgrade_schema


@event.listens_for(Engine, 'connect')
def sqlite_foreign_keys(dbapi_connection, connection_record):
    if dbapi_connection.__class__.__module__.startswith('sqlite3'):
        cursor = dbapi_connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_path=str(BASE_DIR / 'instance'))
    app.config.from_object(Config)
    if test_config:
        app.config.update(test_config)
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    if not app.config.get('SECRET_KEY'):
        path = Path(app.instance_path) / '.local-secret'
        if not path.exists():
            path.write_text(secrets.token_hex(32), encoding='utf-8')
        app.config['SECRET_KEY'] = path.read_text(encoding='utf-8').strip()
    Path(app.config['UPLOAD_FOLDER']).mkdir(parents=True, exist_ok=True)
    (Path(app.config['UPLOAD_FOLDER']) / 'items').mkdir(exist_ok=True)
    (Path(app.config['UPLOAD_FOLDER']) / 'claims').mkdir(exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message_category = 'warning'
    csrf.init_app(app)

    from .auth import auth_bp
    from .routes import main_bp
    from .student import student_bp
    from .admin import admin_bp
    for bp in (auth_bp, main_bp, student_bp, admin_bp):
        app.register_blueprint(bp)

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id)) if str(user_id).isdigit() else None

    @app.before_request
    def enforce_admin_password_change():
        if (current_user.is_authenticated and current_user.is_admin
                and current_user.must_change_password
                and request.endpoint not in {'auth.change_password', 'auth.logout', 'static'}):
            flash('Change the default administrator password before continuing.', 'warning')
            return redirect(url_for('auth.change_password'))

    @app.context_processor
    def template_context():
        return {'categories': ['Electronics', 'Bags', 'Documents', 'Keys', 'Clothing',
                               'Accessories', 'Books', 'Other']}

    @app.errorhandler(404)
    def not_found(error):
        return render_template('error.html', title='Page not found', code=404), 404

    @app.errorhandler(413)
    def upload_too_large(error):
        return render_template('error.html', title='Upload too large (max 6 MB image)', code=413), 413

    @app.errorhandler(403)
    def forbidden(error):
        return render_template('error.html', title='Access denied', code=403), 403

    @app.errorhandler(400)
    def bad_request(error):
        return render_template('error.html', title='Invalid request', code=400), 400

    @app.errorhandler(500)
    def server_error(error):
        db.session.rollback()
        return render_template('error.html', title='Something went wrong', code=500), 500

    @app.cli.command('init-db')
    def init_db_cmd():
        with app.app_context():
            upgrade_schema()
            seed_default_admin(app)
        click.echo('Database ready; existing records preserved.')

    @app.cli.command('change-admin-password')
    @click.option('--email', default=None, help='Administrator email')
    def admin_password_cmd(email):
        from werkzeug.security import generate_password_hash
        import getpass
        email = (email or app.config['ADMIN_EMAIL']).strip().lower()
        with app.app_context():
            user = User.query.filter_by(email=email, role='admin').first()
            if not user:
                click.echo('Admin account not found.'); return
            password = getpass.getpass('New admin password (min 12 characters): ')
            if len(password) < 12:
                click.echo('Password too short.'); return
            user.set_password(password)
            user.must_change_password = False
            db.session.commit()
            click.echo('Admin password updated.')

    # For local Windows beginner use, the first launch creates tables without dropping data.
    # Tests pass INIT_DB=False to control setup per fixture.
    if app.config.get('INIT_DB', True):
        with app.app_context():
            upgrade_schema()
            seed_default_admin(app)

    return app


def seed_default_admin(app):
    # Only create the default on an installation that doesn't already have an admin.
    if User.query.filter_by(role='admin').first():
        return
    admin = User(name='CampusFind Administrator',
                 email=app.config['ADMIN_EMAIL'].strip().lower(), role='admin',
                 must_change_password=True)
    admin.set_password(app.config['ADMIN_PASSWORD'])
    db.session.add(admin)
    db.session.commit()
