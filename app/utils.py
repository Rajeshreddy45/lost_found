"""Validation, uploads, fingerprints and role protection."""
import hashlib
import io
import re
import uuid
from datetime import date, datetime, timedelta
from functools import wraps
from pathlib import Path

from flask import abort, current_app, flash, redirect, url_for
from flask_login import current_user
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import func
from werkzeug.utils import secure_filename

from .extensions import db
from .models import Item, utcnow

ALLOWED_UPLOAD_EXTS = {'.jpg', '.jpeg', '.png', '.webp'}
ALLOWED_IMAGE_FORMATS = {'JPEG', 'PNG', 'WEBP'}
ALLOWED_CATEGORIES = {'Electronics', 'Bags', 'Documents', 'Keys',
                      'Clothing', 'Accessories', 'Books', 'Other'}


def student_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'student':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def admin_only(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.role != 'admin':
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def cleaned(value):
    return ' '.join((value or '').strip().split())


def validate_report(form):
    name = cleaned(form.get('name'))
    desc = cleaned(form.get('description'))
    location = cleaned(form.get('location'))
    category = cleaned(form.get('category'))
    contact = cleaned(form.get('contact_info'))
    if not 3 <= len(name) <= 100:
        raise ValueError('Item name must have 3–100 characters.')
    if category not in ALLOWED_CATEGORIES:
        raise ValueError('Choose a valid item category.')
    if not 12 <= len(desc) <= 2000:
        raise ValueError('Description must have 12–2000 characters.')
    if not 2 <= len(location) <= 120:
        raise ValueError('Location must have 2–120 characters.')
    if not 5 <= len(contact) <= 140:
        raise ValueError('Contact details must have 5–140 characters.')
    try:
        event_date = date.fromisoformat(form.get('event_date', ''))
        event_time = datetime.strptime(form.get('event_time', ''), '%H:%M').time()
    except (ValueError, TypeError):
        raise ValueError('Enter a valid date and time.')
    if event_date > date.today():
        raise ValueError('The reported event date cannot be in the future.')
    if event_date < date.today() - timedelta(days=730):
        raise ValueError('Choose a date within the last 2 years.')
    if event_date == date.today() and event_time > datetime.now().time():
        raise ValueError('The event time cannot be in the future.')
    return dict(name=name, description=desc, location=location, category=category,
                contact_info=contact, event_date=event_date, event_time=event_time)


def report_fingerprint(report_type, data):
    raw = '|'.join([report_type, data['name'].lower(), data['description'].lower(),
                    data['location'].lower(), str(data['event_date']), str(data['event_time'])])
    return hashlib.sha256(raw.encode('utf8')).hexdigest()


def save_image(file, kind):
    """Verify file signature, dimensions, and decode; re-encode as safe RGB JPEG.

    Returns generated filename, or None for optional uploads. Does not trust the
    uploaded filename or MIME header. JPEG sanitization strips metadata.
    """
    if not file or not getattr(file, 'filename', ''):
        return None
    original = secure_filename(file.filename)
    if Path(original).suffix.lower() not in ALLOWED_UPLOAD_EXTS:
        raise ValueError('Images must be JPG, JPEG, PNG or WEBP.')
    payload = file.read(current_app.config['MAX_IMAGE_BYTES'] + 1)
    if len(payload) > current_app.config['MAX_IMAGE_BYTES']:
        raise ValueError('Image must be smaller than 6 MB.')
    if not payload:
        raise ValueError('The uploaded image is empty.')
    try:
        Image.MAX_IMAGE_PIXELS = 20_000_000
        source = Image.open(io.BytesIO(payload))
        if source.format not in ALLOWED_IMAGE_FORMATS:
            raise ValueError('Unsupported image encoding.')
        source.verify()
        img = Image.open(io.BytesIO(payload))
        img = ImageOps.exif_transpose(img)
        if img.width < 20 or img.height < 20 or img.width * img.height > 20_000_000:
            raise ValueError('Image dimensions must be between 20px and 20 megapixels.')
        img = img.convert('RGB')
        img.thumbnail((1600, 1600))
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError):
        raise ValueError('The image is unreadable or unsafe.')
    filename = uuid.uuid4().hex + '.jpg'
    dest = Path(current_app.config['UPLOAD_FOLDER']) / kind / filename
    img.save(dest, 'JPEG', quality=88, optimize=True)
    return filename


def delete_image(filename, kind):
    if filename:
        (Path(current_app.config['UPLOAD_FOLDER']) / kind / filename).unlink(missing_ok=True)
