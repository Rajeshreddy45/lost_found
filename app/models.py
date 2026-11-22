"""Relational schema, with a single source of truth for item/claim states."""
from datetime import datetime, timezone
from flask_login import UserMixin
from sqlalchemy import CheckConstraint, Index, UniqueConstraint
from werkzeug.security import check_password_hash, generate_password_hash
from .extensions import db


def utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(200), unique=True, nullable=False, index=True)
    student_id = db.Column(db.String(40), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(12), nullable=False, default='student', index=True)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    items = db.relationship('Item', foreign_keys='Item.user_id', back_populates='owner', lazy='dynamic')
    claims = db.relationship('Claim', foreign_keys='Claim.user_id', back_populates='claimant', lazy='dynamic')
    __table_args__ = (CheckConstraint("role IN ('student','admin')", name='ck_role'),)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    @property
    def is_admin(self):
        return self.role == 'admin'


class Item(db.Model):
    __tablename__ = 'items'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    report_type = db.Column(db.String(8), nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    category = db.Column(db.String(40), nullable=False, index=True)
    description = db.Column(db.Text, nullable=False)
    location = db.Column(db.String(120), nullable=False)
    event_date = db.Column(db.Date, nullable=False, index=True)
    event_time = db.Column(db.Time, nullable=False)
    image_filename = db.Column(db.String(100), nullable=True)
    contact_info = db.Column(db.String(140), nullable=False)
    status = db.Column(db.String(22), nullable=False, default='approved', index=True)
    flagged_reason = db.Column(db.String(200), nullable=True)
    fingerprint = db.Column(db.String(64), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow, index=True)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    owner = db.relationship('User', foreign_keys=[user_id], back_populates='items')
    __table_args__ = (
        UniqueConstraint('user_id', 'report_type', 'fingerprint', name='uq_user_report_fingerprint'),
        CheckConstraint("report_type IN ('lost','found')", name='ck_report_type'),
        CheckConstraint("status IN ('approved','pending_review','rejected','returned')", name='ck_item_status'),
        Index('ix_item_type_status_date', 'report_type', 'status', 'created_at'),
    )


class Match(db.Model):
    __tablename__ = 'matches'
    id = db.Column(db.Integer, primary_key=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True)
    found_item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True)
    text_score = db.Column(db.Float, nullable=False)
    image_score = db.Column(db.Float, nullable=True)
    category_score = db.Column(db.Float, nullable=False)
    location_score = db.Column(db.Float, nullable=False)
    datetime_score = db.Column(db.Float, nullable=False)
    total_score = db.Column(db.Float, nullable=False, index=True)
    level = db.Column(db.String(20), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=utcnow, onupdate=utcnow)
    lost_item = db.relationship('Item', foreign_keys=[lost_item_id])
    found_item = db.relationship('Item', foreign_keys=[found_item_id])
    __table_args__ = (UniqueConstraint('lost_item_id', 'found_item_id', name='uq_lost_found'),
                      CheckConstraint('lost_item_id != found_item_id', name='ck_distinct_items'))


class Claim(db.Model):
    __tablename__ = 'claims'
    id = db.Column(db.Integer, primary_key=True)
    found_item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    lost_item_id = db.Column(db.Integer, db.ForeignKey('items.id', ondelete='SET NULL'), nullable=True)
    ownership_details = db.Column(db.Text, nullable=False)
    distinguishing_features = db.Column(db.Text, nullable=False)
    evidence_filename = db.Column(db.String(100), nullable=True)
    status = db.Column(db.String(20), nullable=False, default='submitted', index=True)
    admin_note = db.Column(db.Text, nullable=True)
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    claimant = db.relationship('User', foreign_keys=[user_id], back_populates='claims')
    reviewer = db.relationship('User', foreign_keys=[reviewed_by_id])
    found_item = db.relationship('Item', foreign_keys=[found_item_id])
    lost_item = db.relationship('Item', foreign_keys=[lost_item_id])
    __table_args__ = (
        UniqueConstraint('user_id', 'found_item_id', name='uq_claim_user_found'),
        CheckConstraint("status IN ('submitted','under_review','approved','rejected')", name='ck_claim_status'),
    )
