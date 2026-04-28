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


def find_orig_span(orig: str, ev_text: str) -> tuple[int, int] | None:
    """Locate ev_text in the original page text (fuzzy via normalized form)."""
    orig_norm = normalize_for_match(orig)
    ev_norm = normalize_for_match(ev_text)
    if not ev_norm:
        return None
    pos_norm = orig_norm.find(ev_norm)
    phrase_len = len(ev_norm)
    if pos_norm < 0:
        ev_words = ev_norm.split()
        if len(ev_words) < 6:
            return None
        for window in range(min(len(ev_words), 20), 5, -1):
            for i in range(len(ev_words) - window + 1):
                phrase = " ".join(ev_words[i:i + window])
                found = orig_norm.find(phrase)
                if found >= 0:
                    pos_norm = found
                    phrase_len = len(phrase)
                    break
            if pos_norm >= 0:
                break
    if pos_norm < 0:
        return None
    first_words = orig_norm[pos_norm:pos_norm + min(40, phrase_len)].split()
    if not first_words:
        return None
    for first_w in first_words[:3]:
        if len(first_w) < 3:
            continue
        pattern = re.escape(first_w)
        for m in re.finditer(pattern, orig, re.IGNORECASE):
            tail_norm = normalize_for_match(orig[m.start():m.start() + phrase_len + 100])
            if tail_norm.startswith(orig_norm[pos_norm:pos_norm + min(30, phrase_len)]):
                start = m.start()
                end = start
                consumed_norm = 0
                while end < len(orig) and consumed_norm < phrase_len:
                    if not orig[end].isspace():
                        consumed_norm += 1
                    end += 1
                return (start, end)
        break
    return None
