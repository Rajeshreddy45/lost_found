"""Public-facing browse, item details and privacy-aware image serving."""
from pathlib import Path
from flask import Blueprint, abort, current_app, render_template, request, send_from_directory
from flask_login import current_user, login_required
from sqlalchemy import or_

from .extensions import db
from .models import Claim, Item, Match
from .utils import ALLOWED_CATEGORIES

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    recent = (Item.query.filter_by(status='approved', report_type='found')
              .order_by(Item.created_at.desc()).limit(6).all())
    metrics = {
        'reports': Item.query.filter(Item.status.in_(['approved', 'returned'])).count(),
        'found': Item.query.filter_by(status='approved', report_type='found').count(),
        'returned': Item.query.filter_by(status='returned', report_type='found').count(),
    }
    return render_template('index.html', title='Find what matters', recent=recent, metrics=metrics)


@main_bp.route('/items')
def browse():
    query = request.args.get('q', '').strip()[:100]
    report_type = request.args.get('type', 'all')
    category = request.args.get('category', 'all')
    location = request.args.get('location', '').strip()[:100]
    items = Item.query.filter(Item.status.in_(['approved', 'returned']))
    if report_type in ('lost', 'found'):
        items = items.filter_by(report_type=report_type)
    if category in ALLOWED_CATEGORIES:
        items = items.filter_by(category=category)
    if query:
        search = f'%{query}%'
        items = items.filter(or_(Item.name.ilike(search), Item.description.ilike(search)))
    if location:
        items = items.filter(Item.location.ilike(f'%{location}%'))
    items = items.order_by(Item.created_at.desc()).limit(120).all()
    claimed_item_ids = set()
    if current_user.is_authenticated and not current_user.is_admin:
        claimed_item_ids = {cl.found_item_id for cl in Claim.query.filter_by(user_id=current_user.id).all()}
    return render_template('browse.html', title='Browse reports', items=items,
                           claimed_item_ids=claimed_item_ids, q=query,
                           selected_type=report_type, selected_category=category, location=location)


@main_bp.route('/items/<int:item_id>')
def item_detail(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status not in ('approved', 'returned') and not (
            current_user.is_authenticated and (current_user.is_admin or current_user.id == item.user_id)):
        abort(404)
    already_claimed = False
    if current_user.is_authenticated and not current_user.is_admin:
        already_claimed = Claim.query.filter_by(user_id=current_user.id, found_item_id=item.id).first() is not None
    return render_template('item_detail.html', title=item.name, item=item, already_claimed=already_claimed)


@main_bp.route('/media/item/<int:item_id>')
def item_image(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status not in ('approved', 'returned') and not (
            current_user.is_authenticated and (current_user.is_admin or current_user.id == item.user_id)):
        abort(404)
    if not item.image_filename:
        abort(404)
    return send_from_directory(Path(current_app.config['UPLOAD_FOLDER']) / 'items',
                               item.image_filename, mimetype='image/jpeg', max_age=3600)


@main_bp.route('/media/claim/<int:claim_id>')
@login_required
def claim_image(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    if not current_user.is_admin and claim.user_id != current_user.id:
        abort(403)
    if not claim.evidence_filename:
        abort(404)
    return send_from_directory(Path(current_app.config['UPLOAD_FOLDER']) / 'claims',
                               claim.evidence_filename, mimetype='image/jpeg', max_age=0)
