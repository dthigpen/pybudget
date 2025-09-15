import re
from difflib import SequenceMatcher
from typing import List, Tuple, Dict, Any


STOPWORDS = {
    'store',
    'order',
    'number',
    'pickup',
    'payment',
    'online',
    'location',
    'supercenter',
    'shop',
    'inc',
    'co',
    'llc',
}


def tokenize(text: str) -> set[str]:
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]+', ' ', text)
    words = text.split()
    return {word for word in words if word not in STOPWORDS}


def word_token_overlap_score(a: str, b: str) -> float:
    tokens_a = tokenize(a)
    tokens_b = tokenize(b)
    if not tokens_a or not tokens_b:
        return 0.0
    common = tokens_a & tokens_b
    return len(common) / len(tokens_a)


def fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def suggest_categories(
    uncategorized_desc: str,
    known_transactions: List[Dict[str, Any]],
    top_n: int = 3,
    min_overlap_score: float = 0.4,
    fallback_min_fuzzy_score: float = 0.7,
) -> List[Tuple[str, float]]:
    """Return ranked list of (category, score) suggestions."""
    suggestions = []
    uncategorized_desc = uncategorized_desc.strip()

    for txn in known_transactions:
        cat = txn.get('category')
        desc = txn.get('description', '')
        if not cat or cat.lower() == 'uncategorized':
            continue

        overlap = word_token_overlap_score(uncategorized_desc, desc)
        if overlap >= min_overlap_score:
            suggestions.append((cat, overlap))
        else:
            fuzzy = fuzzy_score(uncategorized_desc.lower(), desc.lower())
            if fuzzy >= fallback_min_fuzzy_score:
                suggestions.append((cat, fuzzy * 0.8))

    if not suggestions:
        return []

    # Deduplicate by category, keep best score
    seen = {}
    for cat, score in suggestions:
        if cat not in seen or score > seen[cat]:
            seen[cat] = score

    final = sorted(seen.items(), key=lambda x: x[1], reverse=True)
    return final[:top_n]
