"""Administration: exceptional report review and verified claim outcomes."""
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from .extensions import db
from .matching import generate_matches, remove_matches_for_item
from .models import Claim, Item, Match, User, utcnow
from .utils import admin_only, delete_image

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


@admin_bp.route('/')
@login_required
@admin_only
def dashboard():
    stats = {'students': User.query.filter_by(role='student').count(),
             'reports': Item.query.count(),
             'approved': Item.query.filter_by(status='approved').count(),
             'pending': Item.query.filter_by(status='pending_review').count(),
             'matches': Match.query.count(),
             'claims': Claim.query.filter(Claim.status.in_(['submitted', 'under_review'])).count(),
             'returned': Item.query.filter_by(status='returned', report_type='found').count()}
    recent_claims = Claim.query.order_by(Claim.created_at.desc()).limit(7).all()
    recent_reports = Item.query.order_by(Item.created_at.desc()).limit(7).all()
    return render_template('admin/dashboard.html', title='Admin overview', stats=stats,
                           recent_claims=recent_claims, recent_reports=recent_reports)


@admin_bp.route('/reports')
@login_required
@admin_only
def reports():
    q = request.args.get('q', '').strip()[:100]
    status = request.args.get('status', 'all')
    records = Item.query
    if status in ('approved', 'pending_review', 'rejected', 'returned'):
        records = records.filter_by(status=status)
    if q:
        records = records.filter(or_(Item.name.ilike(f'%{q}%'), Item.location.ilike(f'%{q}%')))
    records = records.order_by(Item.created_at.desc()).limit(300).all()
    return render_template('admin/reports.html', title='Manage reports', reports=records, q=q, status=status)


@admin_bp.route('/reports/<int:item_id>/approve', methods=['POST'])
@login_required
@admin_only
def approve_report(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status != 'pending_review':
        flash('Only reports under review can be approved.', 'warning')
    else:
        item.status = 'approved'
        item.flagged_reason = None
        db.session.commit()
        try:
            generate_matches(item)
        except Exception:
            db.session.rollback()
            current_app.logger.exception('Matching failed during approval')
            flash('Report approved but matching failed. Check the server log.', 'warning')
        else:
            flash('Report approved and AI matches updated.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/reports/<int:item_id>/reject', methods=['POST'])
@login_required
@admin_only
def reject_report(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status != 'pending_review':
        flash('Only pending reports may be rejected.', 'warning')
    else:
        item.status = 'rejected'
        db.session.commit()
        flash('Suspicious report rejected.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/reports/<int:item_id>/delete', methods=['POST'])
@login_required
@admin_only
def delete_report(item_id):
    item = db.get_or_404(Item, item_id)
    if item.status == 'returned':
        flash('Returned item history is retained for audit and cannot be deleted here.', 'warning')
        return redirect(url_for('admin.reports'))
    image = item.image_filename
    evidence = [c.evidence_filename for c in Claim.query.filter_by(found_item_id=item_id).all()]
    # Foreign keys are ON. SET NULL linked lost items; CASCADE claims on found.
    remove_matches_for_item(item_id)
    Claim.query.filter_by(lost_item_id=item_id).update({'lost_item_id': None}, synchronize_session=False)
    Claim.query.filter_by(found_item_id=item_id).delete(synchronize_session=False)
    db.session.delete(item)
    db.session.commit()
    delete_image(image, 'items')
    for filename in evidence:
        delete_image(filename, 'claims')
    flash('Report removed.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/claims')
@login_required
@admin_only
def claims():
    status = request.args.get('status', 'all')
    records = Claim.query
    if status in ('submitted', 'under_review', 'approved', 'rejected'):
        records = records.filter_by(status=status)
    records = records.order_by(Claim.created_at.desc()).limit(250).all()
    return render_template('admin/claims.html', title='Review claims', claims=records, status=status)


@admin_bp.route('/claims/<int:claim_id>/review', methods=['POST'])
@login_required
@admin_only
def review_claim(claim_id):
    claim = db.get_or_404(Claim, claim_id)
    action = request.form.get('action', '')
    note = request.form.get('admin_note', '').strip()[:1000]
    if action not in ('under_review', 'approve', 'reject'):
        abort(400)
    if claim.status in ('approved', 'rejected'):
        flash('This claim has already received a final decision.', 'warning')
        return redirect(url_for('admin.claims'))
    if action == 'approve':
        found = claim.found_item
        if found.status != 'approved':
            flash('This found report is no longer eligible for approval.', 'danger')
            return redirect(url_for('admin.claims'))
        claim.status = 'approved'
        found.status = 'returned'
        if claim.lost_item is not None and claim.lost_item.status == 'approved':
            claim.lost_item.status = 'returned'
        # All other undecided requests are rejected when the item is returned.
        for other in Claim.query.filter(Claim.found_item_id == found.id, Claim.id != claim.id,
                                       Claim.status.in_(['submitted', 'under_review'])).all():
            other.status = 'rejected'
            other.admin_note = 'Another claim was verified and the item was returned.'
            other.reviewed_by_id = current_user.id
            other.reviewed_at = utcnow()
        flash('Ownership claim approved. Item marked as returned.', 'success')
    elif action == 'reject':
        claim.status = 'rejected'
        flash('Claim rejected. Item remains available.', 'info')
    else:
        claim.status = 'under_review'
        flash('Claim moved to Under Review.', 'info')
    claim.admin_note = note
    claim.reviewed_by_id = current_user.id
    claim.reviewed_at = utcnow()
    db.session.commit()
    return redirect(url_for('admin.claims'))


@admin_bp.route('/reports/<int:item_id>/mark-returned', methods=['POST'])
@login_required
@admin_only
def mark_returned(item_id):
    item = db.get_or_404(Item, item_id)
    # Returned is a consequence of a verified claim, never a similarity score.
    verified = Claim.query.filter_by(found_item_id=item.id, status='approved').first()
    if item.report_type != 'found' or not verified:
        flash('An admin-approved ownership claim is required before marking Returned.', 'danger')
    else:
        item.status = 'returned'
        db.session.commit()
        flash('Item marked as returned.', 'success')
    return redirect(url_for('admin.reports'))


@admin_bp.route('/matches')
@login_required
@admin_only
def matches():
    records = Match.query.order_by(Match.total_score.desc()).limit(250).all()
    return render_template('admin/matches.html', title='AI matches', matches=records)


@admin_bp.route('/students')
@login_required
@admin_only
def students():
    records = User.query.filter_by(role='student').order_by(User.created_at.desc()).limit(250).all()
    return render_template('admin/students.html', title='Students', students=records)
