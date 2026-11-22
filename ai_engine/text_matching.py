"""TF–IDF (word unigrams/bigrams) with cosine similarity, no API required."""
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def text_similarity(query, candidates):
    """Return one real cosine score per candidate. Handles sparse/empty input."""
    if not candidates:
        return []
    corpus = [(query or '').strip()] + [(x or '').strip() for x in candidates]
    if not any(corpus):
        return [0.0] * len(candidates)
    vectorizer = TfidfVectorizer(strip_accents='unicode', lowercase=True,
                                 ngram_range=(1, 2), sublinear_tf=True,
                                 token_pattern=r'(?u)\b\w+\b')
    try:
        matrix = vectorizer.fit_transform(corpus)
    except ValueError:
        return [0.0] * len(candidates)
    result = cosine_similarity(matrix[0:1], matrix[1:]).ravel()
    return [float(max(0.0, min(1.0, x))) for x in result]
