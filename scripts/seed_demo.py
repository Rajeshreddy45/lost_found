"""OPTIONAL: insert clearly labeled synthetic demonstration reports.

Creates realistic-looking example records in a real database and computes genuine
TF-IDF/OpenCV scores. Does NOT insert fabricated Match rows.
"""
from datetime import date, datetime, timedelta, time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from app import create_app
from app.extensions import db
from app.matching import generate_matches
from app.models import Item, User
from app.utils import report_fingerprint


def picture(dest, label, hue):
    img = Image.new('RGB', (560, 400), '#e9edf5')
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle((160, 65, 390, 335), 22, fill=hue, outline='#253c55', width=10)
    draw.arc((215, 35, 340, 155), 185, 360, fill='#263d52', width=13)
    draw.rectangle((195, 135, 350, 195), fill='#31517a')
    draw.rounded_rectangle((200, 235, 345, 305), 14, fill='#243f63')
    draw.ellipse((355, 235, 375, 260), fill='#4db5ef')
    img.save(dest, quality=90)


def user(email, name):
    result = User.query.filter_by(email=email).first()
    if result:
        return result
    result = User(email=email, name=name, role='student')
    result.set_password('DemoStudent123')
    db.session.add(result)
    db.session.commit()
    return result


def add_item(owner, typ, name, description, category, location, when_date, when_time, filename):
    values = {'name': name, 'description': description, 'category': category,
              'location': location, 'event_date': when_date, 'event_time': when_time,
              'contact_info': 'demo@example.invalid'}
    fingerprint = report_fingerprint(typ, values)
    found = Item.query.filter_by(user_id=owner.id, report_type=typ, fingerprint=fingerprint).first()
    if found: return found
    item = Item(user_id=owner.id, report_type=typ, fingerprint=fingerprint,
                image_filename=filename, status='approved', **values)
    db.session.add(item); db.session.commit(); return item


def main():
    app = create_app()
    with app.app_context():
        owner1 = user('demo.alex@example.invalid', 'Demo Alex')
        owner2 = user('demo.jamie@example.invalid', 'Demo Jamie')
        folder = Path(app.config['UPLOAD_FOLDER']) / 'items'
        photo1, photo2 = 'demo-blue-bag-lost.jpg', 'demo-blue-bag-found.jpg'
        for name in (photo1, photo2):
            if not (folder / name).exists(): picture(folder / name, 'backpack', '#1d467b')
        event_date = date.today() - timedelta(days=1)
        lost = add_item(owner1, 'lost', 'Blue canvas backpack',
            'Dark blue canvas backpack with red zipper and a small silver keyring.',
            'Bags', 'Central Library', event_date, time(11, 0), photo1)
        found = add_item(owner2, 'found', 'Blue canvas backpack',
            'Dark blue canvas backpack with red zipper and a small silver keyring.',
            'Bags', 'Central Library', event_date, time(11, 15), photo2)
        matches = generate_matches(found)
        print(f'Added or reused {lost.id=} and {found.id=}. Real candidate score: {matches[0]["total"]:.1%}' if matches else 'No matches generated')
        print('Demo student accounts: demo.alex@example.invalid / DemoStudent123 and demo.jamie@example.invalid / DemoStudent123')
        print('These are synthetic example reports, not real campus incidents.')


if __name__ == '__main__':
    main()
