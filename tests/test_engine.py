"""Executable independent AI checks; does not require Flask to be installed."""
from datetime import date, time, timedelta
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import cv2

from ai_engine.text_matching import text_similarity
from ai_engine.image_matching import image_similarity
from ai_engine.matching_engine import (datetime_similarity, match_level, score_candidates,
                                       weighted_score, location_similarity)


def test_tfidf_cosine_similarity():
    sims = text_similarity('black backpack with red zipper',
                           ['black backpack with red zipper', 'silver laboratory microscope'])
    assert len(sims) == 2
    assert 0 <= sims[1] < sims[0] <= 1
    assert sims[0] > .99


def test_weighted_redistributes_missing_image():
    parts = dict(text=.8, image=None, category=1., location=1., datetime=1.)
    expected = (.8*.35 + .15 + .10 + .05) / (.35+.15+.10+.05)
    assert abs(weighted_score(parts) - expected) < 1e-8
    assert weighted_score({'image': None}) == 0


def test_levels_configurable():
    assert match_level(.81) == 'Strong'
    assert match_level(.60) == 'Possible'
    assert match_level(.59) == 'Weak'
    assert match_level(.75, strong=.7) == 'Strong'


def test_location_and_temporal_similarity():
    assert location_similarity('Central Library', 'Central Library') == 1
    assert location_similarity('Central Library', 'Hostel Gate') < .5
    today = date.today()
    same = datetime_similarity(today, time(10), today, time(10))
    distant = datetime_similarity(today, time(10), today - timedelta(days=90), time(1))
    assert same == 1
    assert distant < .2


def test_local_opencv_image_matching(tmp_path):
    rng = np.random.default_rng(42)
    img = rng.integers(0, 256, (210, 260, 3), dtype=np.uint8)
    a, b, c = [tmp_path / x for x in ('a.png', 'b.png', 'c.png')]
    cv2.imwrite(str(a), img)
    cv2.imwrite(str(b), img)
    cv2.imwrite(str(c), 255-img)
    assert image_similarity(a, b) > .95
    assert image_similarity(a, c) < image_similarity(a, b)
    assert image_similarity(a, tmp_path/'missing.png') is None


def make_item(name, desc, category, location, date, time_, image=None):
    return SimpleNamespace(name=name, description=desc, category=category,
                           location=location, event_date=date, event_time=time_, image_filename=image)


def test_rank_real_pairs_without_images(tmp_path):
    day = date.today()
    query = make_item('Black backpack', 'Black canvas backpack with blue keychain', 'Bags', 'Library', day, time(9))
    good = make_item('Black backpack', 'Black canvas backpack with blue keychain', 'Bags', 'Library', day, time(9))
    bad = make_item('Lab microscope', 'Large white research microscope', 'Electronics', 'Hostel', day-timedelta(days=21), time(20))
    results = score_candidates(query, [bad, good], upload_folder=tmp_path)
    assert results[0]['candidate'] is good
    assert results[0]['scores']['image'] is None
    assert results[0]['total'] > results[1]['total']
    assert results[0]['level'] == 'Strong'
