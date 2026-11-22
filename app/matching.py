"""Persist freshly-computed local TF-IDF + OpenCV match suggestions."""
from flask import current_app
from sqlalchemy import or_
from .extensions import db
from .models import Item, Match
from ai_engine.matching_engine import score_candidates


def generate_matches(item):
    if item.status != 'approved':
        return []
    opposite = 'found' if item.report_type == 'lost' else 'lost'
    candidates = Item.query.filter_by(report_type=opposite, status='approved').filter(Item.id != item.id).all()
    scored = score_candidates(item, candidates, upload_folder=current_app.config['UPLOAD_FOLDER'],
                              weights=current_app.config['MATCH_WEIGHTS'],
                              strong=current_app.config['MATCH_STRONG_THRESHOLD'],
                              possible=current_app.config['MATCH_POSSIBLE_THRESHOLD'])
    for result in scored:
        other = result['candidate']
        lost_id, found_id = (item.id, other.id) if item.report_type == 'lost' else (other.id, item.id)
        match = Match.query.filter_by(lost_item_id=lost_id, found_item_id=found_id).first()
        if match is None:
            match = Match(lost_item_id=lost_id, found_item_id=found_id)
            db.session.add(match)
        part = result['scores']
        match.text_score = part['text']
        match.image_score = part['image']
        match.category_score = part['category']
        match.location_score = part['location']
        match.datetime_score = part['datetime']
        match.total_score = result['total']
        match.level = result['level']
    db.session.commit()
    return scored


def matches_for_user(user_id, limit=30):
    return (Match.query.join(Item, Match.lost_item_id == Item.id)
            .filter(or_(Item.user_id == user_id,
                        Match.found_item_id.in_(db.session.query(Item.id).filter_by(user_id=user_id))))
            .order_by(Match.total_score.desc()).limit(limit).all())


def remove_matches_for_item(item_id):
    Match.query.filter(or_(Match.lost_item_id == item_id, Match.found_item_id == item_id)).delete(synchronize_session=False)
