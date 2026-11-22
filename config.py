"""Configuration; no API keys or external ML services are needed."""
import os
from datetime import timedelta
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / '.env')


class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', '')  # generated and stored in instance/ on first run if unset
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///' + str(BASE_DIR / 'instance' / 'campusfind.db').replace('\\', '/'))
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 7 * 1024 * 1024  # entire request, 6 MB max image
    MAX_IMAGE_BYTES = 6 * 1024 * 1024
    UPLOAD_FOLDER = str(BASE_DIR / 'instance' / 'uploads')
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    REMEMBER_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@campusfind.local')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'CampusFind@2026!')
    MATCH_WEIGHTS = {'text': 0.35, 'image': 0.35, 'category': 0.15,
                     'location': 0.10, 'datetime': 0.05}
    MATCH_STRONG_THRESHOLD = float(os.getenv('MATCH_STRONG_THRESHOLD', '0.80'))
    MATCH_POSSIBLE_THRESHOLD = float(os.getenv('MATCH_POSSIBLE_THRESHOLD', '0.60'))
    MAX_REPORTS_PER_HOUR = 8
