"""User authentication, profile and enforced admin password rotation."""
import re
from flask import Blueprint, abort, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required, login_user, logout_user
from sqlalchemy.exc import IntegrityError
from .extensions import db
from .models import User


auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


def safe_destination(target):
    # Only same-site relative destinations, never user-supplied external URLs.
    return target if target and target.startswith('/') and not target.startswith('//') and '\\' not in target else None


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        name = ' '.join(request.form.get('name', '').split())
        email = request.form.get('email', '').strip().lower()
        student_id = request.form.get('student_id', '').strip().upper() or None
        password = request.form.get('password', '')
        confirm = request.form.get('confirm', '')
        if not 3 <= len(name) <= 100:
            flash('Enter your full name (3–100 characters).', 'danger')
        elif not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 200:
            flash('Enter a valid email address.', 'danger')
        elif student_id and (len(student_id) > 40 or not re.fullmatch(r'[A-Z0-9-]+', student_id)):
            flash('Student ID may contain letters, numbers and hyphens.', 'danger')
        elif len(password) < 10 or not re.search('[a-zA-Z]', password) or not re.search('[0-9]', password):
            flash('Password needs 10+ characters, including a letter and a number.', 'danger')
        elif password != confirm:
            flash('The passwords do not match.', 'danger')
        elif User.query.filter_by(email=email).first():
            flash('That email is already registered.', 'danger')
        else:
            user = User(name=name, email=email, student_id=student_id, role='student')
            user.set_password(password)
            db.session.add(user)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                flash('Email or student ID already exists.', 'danger')
            else:
                login_user(user)
                flash('Your account is ready. Welcome!', 'success')
                return redirect(url_for('student.dashboard'))
    return render_template('auth/register.html', title='Create account')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('admin.dashboard') if current_user.is_admin else url_for('student.dashboard'))
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user, remember=False, fresh=True)
            flash('Signed in successfully.', 'success')
            if user.is_admin:
                return redirect(url_for('auth.change_password') if user.must_change_password else url_for('admin.dashboard'))
            return redirect(safe_destination(request.args.get('next')) or url_for('student.dashboard'))
        flash('Incorrect email or password.', 'danger')
    return render_template('auth/login.html', title='Sign in')


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    logout_user()
    flash('You have been signed out.', 'info')
    return redirect(url_for('main.index'))


@auth_bp.route('/profile')
@login_required
def profile():
    return render_template('auth/profile.html', title='My profile')


@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        existing = request.form.get('current_password', '')
        updated = request.form.get('new_password', '')
        confirm = request.form.get('confirm_password', '')
        if not current_user.check_password(existing):
            flash('Current password is incorrect.', 'danger')
        elif len(updated) < 12 or not re.search('[A-Za-z]', updated) or not re.search('[0-9]', updated):
            flash('New password needs 12+ characters, including a letter and a number.', 'danger')
        elif updated != confirm:
            flash('New passwords do not match.', 'danger')
        elif updated == existing:
            flash('Choose a different password.', 'danger')
        else:
            current_user.set_password(updated)
            current_user.must_change_password = False
            db.session.commit()
            flash('Password updated successfully.', 'success')
            return redirect(url_for('admin.dashboard') if current_user.is_admin else url_for('auth.profile'))
    return render_template('auth/change_password.html', title='Change password')
