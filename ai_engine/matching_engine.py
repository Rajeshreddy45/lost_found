"""Explainable weighted multimodal similarity and configurable thresholds."""
import math
import re
from datetime import datetime
from difflib import SequenceMatcher

from .image_matching import image_similarity
from .text_matching import text_similarity

DEFAULT_WEIGHTS = {'text': .35, 'image': .35, 'category': .15,
                   'location': .10, 'datetime': .05}


def normalized_tokens(value):
    return set(re.findall(r'[a-z0-9]+', (value or '').lower()))


def location_similarity(a, b):
    tokens_a, tokens_b = normalized_tokens(a), normalized_tokens(b)
    if not a or not b:
        return 0.0
    jaccard = len(tokens_a & tokens_b) / max(1, len(tokens_a | tokens_b))
    fuzzy = SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
    return max(0.0, min(1.0, .65 * jaccard + .35 * fuzzy))


def datetime_similarity(date_a, time_a, date_b, time_b):
    if not all((date_a, date_b, time_a, time_b)):
        return 0.0
    day_delta = abs((date_a - date_b).days)
    minute_a = time_a.hour * 60 + time_a.minute
    minute_b = time_b.hour * 60 + time_b.minute
    minute_delta = abs(minute_a - minute_b)
    date_score = math.exp(-day_delta / 7)
    time_score = math.exp(-minute_delta / 180)
    return .7 * date_score + .3 * time_score


def weighted_score(parts, weights=None):
    """Omit unavailable modalities; redistribute remaining weights to sum to 1."""
    weights = weights or DEFAULT_WEIGHTS
    available = {key: weights.get(key, 0) for key, value in parts.items()
                 if value is not None and weights.get(key, 0) > 0}
    denominator = sum(available.values())
    if denominator <= 0:
        return 0.0
    return max(0.0, min(1.0, sum(parts[key] * weight for key, weight in available.items()) / denominator))


def match_level(score, strong=.80, possible=.60):
    if score >= strong:
        return 'Strong'
    if score >= possible:
        return 'Possible'
    return 'Weak'


def item_text(item):
    # Repeat short identifying name to give it a useful influence in TF-IDF.
    return f'{item.name} {item.name} {item.description}'


def score_candidates(source, candidates, *, upload_folder, weights=None, strong=.80, possible=.60):
    """Score real opposite-type records and expose each explainable modality."""
    from pathlib import Path
    candidates = list(candidates)
    texts = text_similarity(item_text(source), [item_text(i) for i in candidates])
    results = []
    for candidate, text in zip(candidates, texts):
        src_img = (Path(upload_folder) / 'items' / source.image_filename
                   if source.image_filename else None)
        other_img = (Path(upload_folder) / 'items' / candidate.image_filename
                     if candidate.image_filename else None)
        image = image_similarity(src_img, other_img)
        parts = {
            'text': text,
            'image': image,
            'category': float(source.category == candidate.category),
            'location': location_similarity(source.location, candidate.location),
            'datetime': datetime_similarity(source.event_date, source.event_time,
                                             candidate.event_date, candidate.event_time),
        }
        total = weighted_score(parts, weights)
        results.append({'candidate': candidate, 'scores': parts, 'total': round(total, 5),
                        'level': match_level(total, strong, possible)})
    return sorted(results, key=lambda x: x['total'], reverse=True)
