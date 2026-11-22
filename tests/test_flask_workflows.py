"""End-to-end Flask test-client checks for required workflows. Run with pytest -q."""
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from PIL import Image

from app import create_app
from app.extensions import db
from app.models import Claim, Item, Match, User
from tests.conftest import register, login, logout, report, report_data, admin_login_and_rotate


def test_registration_login_profile_logout(client):
    response = register(client)
    assert response.status_code == 200
    assert b'My reports' in response.data
    profile = client.get('/auth/profile')
    assert b'Student One' in profile.data
    logout(client)
    assert client.get('/auth/profile').status_code == 302
    response = login(client, 'student1@example.edu')
    assert b'My reports' in response.data


def test_lost_and_found_auto_approved_and_matched(client, application):
    register(client)
    assert b'automatically approved' in report(client, 'lost').data.lower()
    logout(client)
    register(client, 'Student Two', 'student2@example.edu', 'S002')
    assert report(client, 'found').status_code == 200
    with application.app_context():
        items = Item.query.order_by(Item.id).all()
        assert len(items) == 2
        assert all(it.status == 'approved' for it in items)
        matches = Match.query.all()
        assert len(matches) == 1
        assert matches[0].total_score > .8
        assert matches[0].level == 'Strong'
    logout(client)
    login(client, 'student1@example.edu')
    results = client.get('/student/reports/1/matches')
    assert results.status_code == 200
    assert b'%</span>' in results.data or b'%' in results.data
    assert b'Black backpack' in results.data


def test_claim_button_visible_only_for_eligible_students(client, application):
    register(client)
    report(client, 'found')
    assert b'Claim This Item' not in client.get('/items/1').data
    logout(client)
    register(client, 'Student Two', 'student2@example.edu', 'S002')
    assert b'Claim This Item' in client.get('/items/1').data
    assert b'Claim This Item' in client.get('/items?type=found').data
    assert client.get('/student/claim/1').status_code == 200


def test_claim_submit_duplicate_prevention_and_admin_approval(client, application):
    register(client)
    report(client, 'lost')
    logout(client)
    register(client, 'Student Two', 'student2@example.edu', 'S002')
    report(client, 'found')
    logout(client)
    login(client, 'student1@example.edu')
    claim_data = {'lost_item_id':'1', 'ownership_details':'I bought the item in September and lost it at the library desk.',
                  'distinguishing_features':'A small blue keychain on the zipper.'}
    response = client.post('/student/claim/2', data=claim_data, follow_redirects=True)
    assert b'Claim submitted' in response.data
    again = client.post('/student/claim/2', data=claim_data, follow_redirects=True)
    assert b'already claimed' in again.data
    with application.app_context():
        assert Claim.query.count() == 1
        assert Claim.query.first().status == 'submitted'
        assert Item.query.get(2).status == 'approved'
    logout(client)
    admin_login_and_rotate(client)
    assert b'Admin overview' in client.get('/admin/').data
    client.post('/admin/claims/1/review', data={'action':'under_review'})
    with application.app_context():
        assert db.session.get(Claim, 1).status == 'under_review'
    result = client.post('/admin/claims/1/review', data={'action':'approve', 'admin_note':'Evidence checked'}, follow_redirects=True)
    assert b'Item marked as returned' in result.data
    with application.app_context():
        assert db.session.get(Claim, 1).status == 'approved'
        assert db.session.get(Item, 2).status == 'returned'
        assert db.session.get(Item, 1).status == 'returned'
    logout(client)
    login(client, 'student1@example.edu')
    assert b'Approved' in client.get('/student/dashboard').data


def test_claim_rejection_does_not_return_item(client, application):
    register(client)
    report(client, 'found')
    logout(client)
    register(client, 'Student Two', 'student2@example.edu', 'S002')
    client.post('/student/claim/1', data={'ownership_details': 'The item was purchased by me this year and was lost yesterday.',
                                          'distinguishing_features': 'Distinct red zipper and blue loop.'})
    logout(client)
    admin_login_and_rotate(client)
    result = client.post('/admin/claims/1/review', data={'action':'reject', 'admin_note':'Incorrect identifying details'}, follow_redirects=True)
    assert result.status_code == 200
    with application.app_context():
        assert db.session.get(Claim, 1).status == 'rejected'
        assert db.session.get(Item, 1).status == 'approved'


def test_duplicate_report_is_prevented(client, application):
    register(client)
    report(client, 'lost')
    again = report(client, 'lost')
    assert b'already submitted this exact report' in again.data
    with application.app_context():
        assert Item.query.count() == 1


def test_invalid_file_rejected(client, application):
    register(client)
    data = report_data()
    data['image'] = (BytesIO(b'not an actual image'), 'fake.png')
    response = client.post('/student/report/lost', data=data, content_type='multipart/form-data')
    assert response.status_code == 400
    with application.app_context():
        assert Item.query.count() == 0


def test_opencv_valid_image_and_storage(client, application):
    register(client)
    img = Image.new('RGB', (128, 128), (180, 80, 50))
    out = BytesIO()
    img.save(out, 'PNG'); out.seek(0)
    data = report_data(); data['image'] = (out, 'sample.png')
    response = client.post('/student/report/lost', data=data)
    assert response.status_code == 302
    with application.app_context():
        item = Item.query.first()
        assert item.image_filename.endswith('.jpg')
        assert (Path(application.config['UPLOAD_FOLDER']) / 'items' / item.image_filename).is_file()
    assert client.get('/media/item/1').status_code == 200


def test_admin_requires_login_role_and_password_rotation(client):
    assert client.get('/admin/').status_code == 302
    register(client)
    assert client.get('/admin/').status_code == 403
    assert client.get('/admin/claims').status_code == 403
    logout(client)
    login(client, 'admin@campusfind.local', 'CampusFind@2026!')
    assert client.get('/admin/').status_code == 302  # must rotate password
    assert b'Change password' in client.get('/auth/change-password').data
    admin_login_and_rotate(client)
    assert client.get('/admin/').status_code == 200


def test_private_contact_not_visible_to_other_students(client):
    register(client)
    report(client, 'found')
    logout(client)
    register(client, 'Student Two', 'student2@example.edu', 'S002')
    response = client.get('/items/1')
    assert response.status_code == 200
    assert b'private-student@example.edu' not in response.data


def test_returned_requires_admin_approved_claim(client, application):
    register(client)
    report(client, 'found')
    logout(client)
    admin_login_and_rotate(client)
    response = client.post('/admin/reports/1/mark-returned', follow_redirects=True)
    assert b'admin-approved ownership claim is required' in response.data
    with application.app_context():
        assert db.session.get(Item, 1).status == 'approved'


def test_suspicious_rate_limited_report_is_reviewed(client, application):
    application.config['MAX_REPORTS_PER_HOUR'] = 1
    register(client)
    report(client, 'lost')
    report(client, 'lost', name='Second blue backpack')
    with application.app_context():
        assert db.session.get(Item, 1).status == 'approved'
        assert db.session.get(Item, 2).status == 'pending_review'
    logout(client)
    admin_login_and_rotate(client)
    client.post('/admin/reports/2/approve')
    with application.app_context():
        assert db.session.get(Item, 2).status == 'approved'


def test_db_init_never_drops_existing_records(application):
    with application.app_context():
        user = User(name='Persistent User', email='persist@example.edu', role='student')
        user.set_password('ExamplePass123'); db.session.add(user); db.session.commit()
    again = create_app({'TESTING': True,
        'SQLALCHEMY_DATABASE_URI': application.config['SQLALCHEMY_DATABASE_URI'],
        'UPLOAD_FOLDER': application.config['UPLOAD_FOLDER'],
        'SECRET_KEY': 'only-in-tests-secret', 'WTF_CSRF_ENABLED': False, 'INIT_DB': True})
    with again.app_context():
        assert User.query.filter_by(email='persist@example.edu').first() is not None


def test_csrf_protection_enabled_by_default(application):
    application.config['WTF_CSRF_ENABLED'] = True
    client = application.test_client()
    response = client.post('/auth/register', data={'name':'CSRF Student', 'email':'csrf@example.edu'})
    assert response.status_code == 400
