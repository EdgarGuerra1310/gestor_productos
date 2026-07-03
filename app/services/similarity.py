import re


def text_similarity(left: str, right: str) -> float:
    left_tokens = _tokens(left)
    right_tokens = _tokens(right)
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


def _tokens(value: str) -> set[str]:
    normalized = value.lower()
    words = re.findall(r"[a-záéíóúñü0-9]{3,}", normalized, flags=re.IGNORECASE)
    return set(words)
