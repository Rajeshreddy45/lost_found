from datetime import date, timedelta
from pathlib import Path
import pytest
from app import create_app
from app.extensions import db


@pytest.fixture
def application(tmp_path):
    app = create_app({
        'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': 'sqlite:///' + str(tmp_path / 'test.db'),
        'UPLOAD_FOLDER': str(tmp_path / 'uploads'),
        'SECRET_KEY': 'only-in-tests-secret',
        'WTF_CSRF_ENABLED': False,
        'ADMIN_EMAIL': 'admin@campusfind.local',
        'ADMIN_PASSWORD': 'CampusFind@2026!',
        'INIT_DB': True,
    })
    yield app
    with app.app_context():
        db.session.remove()
        db.engine.dispose()


@pytest.fixture
def client(application):
    return application.test_client()


def register(client, name='Student One', email='student1@example.edu', student_id='S001'):
    return client.post('/auth/register', data={
        'name': name, 'email': email, 'student_id': student_id,
        'password': 'ExamplePass123', 'confirm': 'ExamplePass123'}, follow_redirects=True)


def login(client, email, password='ExamplePass123'):
    return client.post('/auth/login', data={'email': email, 'password': password}, follow_redirects=True)


def logout(client):
    return client.post('/auth/logout', follow_redirects=True)


def report_data(name='Black backpack', loc='Central Library', desc=None):
    return {
        'name': name, 'category': 'Bags',
        'description': desc or 'A black canvas backpack with a blue keychain and one red stripe.',
        'location': loc, 'event_date': (date.today()-timedelta(days=1)).isoformat(),
        'event_time': '09:30', 'contact_info': 'private-student@example.edu'
    }


def report(client, typ='lost', name='Black backpack', loc='Central Library', desc=None):
    return client.post('/student/report/' + typ, data=report_data(name, loc, desc), follow_redirects=True)


def admin_login_and_rotate(client):
    login(client, 'admin@campusfind.local', 'CampusFind@2026!')
    return client.post('/auth/change-password', data={
        'current_password': 'CampusFind@2026!',
        'new_password': 'ChangedSecurePassword123',
        'confirm_password': 'ChangedSecurePassword123',
    }, follow_redirects=True)
