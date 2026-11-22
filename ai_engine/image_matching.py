"""Local OpenCV image similarity: ORB feature matching + HSV histogram.

This is visual similarity, not object recognition or ownership verification.
"""
from functools import lru_cache
from pathlib import Path
import cv2
import numpy as np


@lru_cache(maxsize=256)
def _features(path):
    img = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    scale = min(1.0, 640.0 / max(h, w))
    if scale < 1.0:
        img = cv2.resize(img, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(nfeatures=600, fastThreshold=12)
    _, descriptors = orb.detectAndCompute(gray, None)
    hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
    hist = cv2.calcHist([hsv], [0, 1], None, [24, 16], [0, 180, 0, 256])
    hist = cv2.normalize(hist, hist).flatten()
    variance = float(np.std(gray))
    return descriptors, hist, variance


def image_similarity(path_a, path_b):
    """Return 0–1, or None when either image is unavailable/unreadable."""
    if not path_a or not path_b:
        return None
    if not Path(path_a).is_file() or not Path(path_b).is_file():
        return None
    a = _features(str(Path(path_a).resolve()))
    b = _features(str(Path(path_b).resolve()))
    if a is None or b is None:
        return None
    desc_a, hist_a, var_a = a
    desc_b, hist_b, var_b = b
    histogram = float(cv2.compareHist(hist_a.astype('float32'),
                                       hist_b.astype('float32'), cv2.HISTCMP_CORREL))
    histogram = max(0.0, min(1.0, histogram))
    if desc_a is not None and desc_b is not None and len(desc_a) >= 2 and len(desc_b) >= 2:
        matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        matches = matcher.knnMatch(desc_a, desc_b, k=2)
        good = sum(1 for pair in matches if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance)
        denom = max(1, min(len(desc_a), len(desc_b)))
        # Features may be sparse even in a genuine visual match; combine with colour.
        feature_score = min(1.0, 2.5 * good / denom)
        result = 0.72 * feature_score + 0.28 * histogram
    else:
        # Flat images have no distinguishable keypoints; avoid treating them as proof.
        result = 0.20 * histogram if min(var_a, var_b) > 8 else 0.0
    return round(max(0.0, min(1.0, float(result))), 5)
