"""Student reports, AI results and evidence-based ownership claims."""
from datetime import timedelta
from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .matching import generate_matches, matches_for_user
from .models import Claim, Item, Match, utcnow
from .utils import (delete_image, report_fingerprint, save_image, student_only,
                    validate_report)

student_bp = Blueprint('student', __name__, url_prefix='/student')


@student_bp.route('/dashboard')
@login_required
@student_only
def dashboard():
    reports = Item.query.filter_by(user_id=current_user.id).order_by(Item.created_at.desc()).all()
    claims = Claim.query.filter_by(user_id=current_user.id).order_by(Claim.created_at.desc()).all()
    matches = matches_for_user(current_user.id, limit=15)
    stats = {'total': len(reports), 'lost': sum(r.report_type == 'lost' for r in reports),
             'found': sum(r.report_type == 'found' for r in reports),
             'approved': sum(r.status == 'approved' for r in reports),
             'pending': sum(r.status == 'pending_review' for r in reports)}
    return render_template('student/dashboard.html', title='My dashboard',
                           reports=reports, claims=claims, matches=matches, stats=stats)


@student_bp.route('/report/<report_type>', methods=['GET', 'POST'])
@login_required
@student_only
def report_new(report_type):
    if report_type not in ('lost', 'found'):
        abort(404)
    if request.method == 'POST':
        try:
            values = validate_report(request.form)
        except ValueError as exc:
            flash(str(exc), 'danger')
            return render_template('student/report_form.html', title='Report an item', report_type=report_type), 400
        fingerprint = report_fingerprint(report_type, values)
        if Item.query.filter_by(user_id=current_user.id, report_type=report_type,
                                fingerprint=fingerprint).first():
            flash('You already submitted this exact report.', 'warning')
            return redirect(url_for('student.dashboard'))
        filename = None
        try:
            # Image optional so users without photos are not excluded; missing modality
            # weight is redistributed in the AI scoring engine.
            filename = save_image(request.files.get('image'), 'items')
            recent_count = Item.query.filter_by(user_id=current_user.id).filter(
                Item.created_at >= utcnow() - timedelta(hours=1)).count()
            flagged = recent_count >= current_app.config['MAX_REPORTS_PER_HOUR']
            item = Item(user_id=current_user.id, report_type=report_type,
                        image_filename=filename, fingerprint=fingerprint, **values,
                        status='pending_review' if flagged else 'approved',
                        flagged_reason='High submission frequency; needs staff review' if flagged else None)
            db.session.add(item)
            db.session.commit()
        except ValueError as exc:
            delete_image(filename, 'items')
            flash(str(exc), 'danger')
            return render_template('student/report_form.html', title='Report an item', report_type=report_type), 400
        except IntegrityError:
            db.session.rollback()
            delete_image(filename, 'items')
            flash('Duplicate report detected.', 'warning')
            return redirect(url_for('student.dashboard'))
        if item.status == 'approved':
            try:
                generated = generate_matches(item)
            except Exception:
                current_app.logger.exception('Matching failed for report #%s', item.id)
                db.session.rollback()
                flash('Report approved; matching could not finish. Please inform the administrator.', 'warning')
            else:
                flash(f'Report automatically approved. Compared with {len(generated)} opposite-type reports.', 'success')
        else:
            flash('Report saved for review due to unusually frequent submissions.', 'warning')
        return redirect(url_for('student.report_matches', item_id=item.id))
    return render_template('student/report_form.html', title='Report an item', report_type=report_type)


@student_bp.route('/reports/<int:item_id>/matches')
@login_required
@student_only
def report_matches(item_id):
    item = db.get_or_404(Item, item_id)
    if item.user_id != current_user.id:
        abort(403)
    if item.report_type == 'lost':
        matches = Match.query.filter_by(lost_item_id=item.id).order_by(Match.total_score.desc()).limit(20).all()
    else:
        matches = Match.query.filter_by(found_item_id=item.id).order_by(Match.total_score.desc()).limit(20).all()
    return render_template('student/matches.html', title='AI match suggestions', item=item, matches=matches)


@student_bp.route('/claim/<int:item_id>', methods=['GET', 'POST'])
@login_required
@student_only
def claim_item(item_id):
    found = db.get_or_404(Item, item_id)
    if found.report_type != 'found' or found.status != 'approved':
        abort(404)
    if found.user_id == current_user.id:
        abort(403)
    if Claim.query.filter_by(user_id=current_user.id, found_item_id=found.id).first():
        flash('You have already claimed this item. Check your dashboard for its status.', 'warning')
        return redirect(url_for('student.dashboard'))
    own_lost = Item.query.filter_by(user_id=current_user.id, report_type='lost', status='approved').order_by(Item.created_at.desc()).all()
    if request.method == 'POST':
        details = ' '.join(request.form.get('ownership_details', '').split())
        features = ' '.join(request.form.get('distinguishing_features', '').split())
        lost_id = request.form.get('lost_item_id', '').strip()
        if not 20 <= len(details) <= 2000 or not 10 <= len(features) <= 1000:
            flash('Give at least 20 characters of ownership details and 10 of distinguishing characteristics.', 'danger')
            return render_template('student/claim_form.html', title='Claim item', item=found, own_lost=own_lost), 400
        linked = None
        if lost_id:
            if not lost_id.isdecimal():
                abort(400)
            linked = db.session.get(Item, int(lost_id))
            if linked is None or linked.user_id != current_user.id or linked.report_type != 'lost' or linked.status != 'approved':
                abort(403)
        filename = None
        try:
            filename = save_image(request.files.get('evidence'), 'claims')
            claim = Claim(found_item_id=found.id, user_id=current_user.id,
                          lost_item_id=linked.id if linked else None,
                          ownership_details=details, distinguishing_features=features,
                          evidence_filename=filename, status='submitted')
            db.session.add(claim)
            db.session.commit()
        except ValueError as exc:
            delete_image(filename, 'claims')
            flash(str(exc), 'danger')
            return render_template('student/claim_form.html', title='Claim item', item=found, own_lost=own_lost), 400
        except IntegrityError:
            db.session.rollback()
            delete_image(filename, 'claims')
            flash('Your claim already exists.', 'warning')
            return redirect(url_for('student.dashboard'))
        flash('Claim submitted. Staff will verify your ownership before return.', 'success')
        return redirect(url_for('student.dashboard'))
    return render_template('student/claim_form.html', title='Claim item', item=found, own_lost=own_lost)
