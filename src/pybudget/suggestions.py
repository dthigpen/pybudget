import re
from difflib import SequenceMatcher
from typing import List, Tuple
from pybudget.types import Transaction

# NOTE could extend these in the pybudget.json
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


def tokenize(text):
    # Lowercase and remove non-alphanumeric characters (except spaces)
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]+', ' ', text)

    # Split into words
    words = text.split()

    # Remove stopwords
    return {word for word in words if word not in STOPWORDS}


def word_token_overlap_score(a: str, b: str):
    tokens_a = tokenize(a)
    tokens_b = tokenize(b)

    if not tokens_a or not tokens_b:
        return 0.0  # Avoid division by zero or meaningless matches

    common = tokens_a & tokens_b
    score = len(common) / len(tokens_a)

    return score


def fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, a, b).ratio()


def suggest_categories(
    uncategorized_desc: str,
    known_transactions: List[Transaction],
    top_n: int = 3,
    min_overlap_score: float = 0.4,
    fallback_min_fuzzy_score: float = 0.7,
) -> List[Tuple[str, float]]:
    """
    Suggest categories for a transaction based on known categorized transactions.

    Returns a list of (category, score) tuples, sorted by descending score.
    """
    suggestions = []
    uncategorized_desc = uncategorized_desc.strip()

    for txn in known_transactions:
        if not txn.category or txn.category.lower() == 'uncategorized':
            continue  # Skip uncategorized entries

        overlap = word_token_overlap_score(uncategorized_desc, txn.description)

        if overlap >= min_overlap_score:
            suggestions.append((txn.category, overlap))
        else:
            fuzzy = fuzzy_score(uncategorized_desc.lower(), txn.description.lower())
            if fuzzy >= fallback_min_fuzzy_score:
                suggestions.append(
                    (txn.category, fuzzy * 0.8)
                )  # Discount fuzzy slightly

    if not suggestions:
        return []

    # Sort by score descending
    suggestions.sort(key=lambda x: x[1], reverse=True)

    # Deduplicate by category, keeping highest score per category
    seen = {}
    for category, score in suggestions:
        if category not in seen or score > seen[category]:
            seen[category] = score

    final = sorted(seen.items(), key=lambda x: x[1], reverse=True)

    return final[:top_n]
