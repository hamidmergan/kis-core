"""Text normalization and evidence matching for card validation."""

import re


def normalize_chunk(text: str) -> str:
    """Remove hyphenation across line breaks and collapse whitespace."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"\s*\n\s*", " ", text)
    return text.strip()


def normalize_for_match(text: str) -> str:
    """Normalize text for fuzzy substring matching (whitespace, punctuation, case)."""
    text = normalize_chunk(text).lower()
    text = re.sub(r"[^\w\säöüß]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_for_segment_lookup(text: str) -> str:
    """Stricter normalization for Whisper segment lookup (including uppercase umlauts)."""
    text = re.sub(r"-\s*\n\s*", "", text)
    text = re.sub(r"[^\w\säöüßÄÖÜ]+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def evidence_matches_page(evidence_norm: str, page_text_norm: str) -> bool:
    """Check whether the evidence appears in the page in full or with 6+ contiguous words."""
    if not evidence_norm or not page_text_norm:
        return False
    if evidence_norm in page_text_norm:
        return True
    ev_words = evidence_norm.split()
    if len(ev_words) < 6:
        return False
    for window in range(min(len(ev_words), 20), 5, -1):
        for i in range(len(ev_words) - window + 1):
            phrase = " ".join(ev_words[i:i + window])
            if phrase in page_text_norm:
                return True
    return False


def is_duplicate_evidence(new_norm: str, seen_norms: list[str]) -> bool:
    """True if new evidence overlaps an already-seen one by >=70%."""
    new_words = new_norm.split()
    if len(new_words) < 4:
        return new_norm in seen_norms
    for seen in seen_norms:
        seen_words = seen.split()
        shorter_len = min(len(new_words), len(seen_words))
        threshold = max(4, int(shorter_len * 0.7))
        for i in range(len(new_words) - threshold + 1):
            phrase = " ".join(new_words[i:i + threshold])
            if phrase in seen:
                return True
    return False


def build_page_text(chunks: list[dict]) -> str:
    """Concatenate chunks of a page and remove overlap between consecutive chunks."""
    result = ""
    for ch in chunks:
        content = (ch.get("content") or "").strip()
        if not content:
            continue
        if not result:
            result = content
            continue
        # Overlap detection: compare the last <=200 chars of the result against the start
        overlap_max = min(200, len(result), len(content))
        best_overlap = 0
        for n in range(overlap_max, 20, -1):
            if result[-n:] == content[:n]:
                best_overlap = n
                break
        if best_overlap > 0:
            result += content[best_overlap:]
        else:
            result += " " + content
    return result
