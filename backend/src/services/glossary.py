import re
from typing import Dict, List, Tuple


class GlossaryService:
    def __init__(self):
        self._entries: Dict[str, str] = {}
        self._patterns: List[Tuple[re.Pattern, str, str]] = []

    @property
    def entries(self) -> Dict[str, str]:
        return self._entries

    @property
    def count(self) -> int:
        return len(self._entries)

    def set_entries(self, entries: Dict[str, str]) -> None:
        normalized = self._normalize(entries)
        self._entries = normalized
        self._patterns = self._build_patterns(normalized)

    def apply_to_text(self, text: str) -> Tuple[str, Dict[str, str]]:
        if not self._patterns:
            return text, {}
        updated = text
        replacements: Dict[str, str] = {}
        for pattern, token, target in self._patterns:
            if pattern.search(updated):
                updated = pattern.sub(token, updated)
                replacements[token] = target
        return updated, replacements

    def restore_text(self, text: str, replacements: Dict[str, str]) -> str:
        restored = text
        for token, target in replacements.items():
            restored = restored.replace(token, target)
        return restored

    @staticmethod
    def _normalize(data) -> Dict[str, str]:
        if not isinstance(data, dict):
            return {}
        normalized: Dict[str, str] = {}
        for key, value in data.items():
            if isinstance(key, str) and isinstance(value, str):
                key = key.strip()
                if key:
                    normalized[key] = value
        return normalized

    @staticmethod
    def _build_patterns(glossary: Dict[str, str]) -> List[Tuple[re.Pattern, str, str]]:
        entries: List[Tuple[re.Pattern, str, str]] = []
        sorted_items = sorted(glossary.items(), key=lambda item: len(item[0]), reverse=True)
        for index, (source, target) in enumerate(sorted_items):
            if not source or not target:
                continue
            token = f"__GLOSSARY_{index}__"
            pattern = re.escape(source)
            if re.match(r"\w", source[0]):
                pattern = r"\b" + pattern
            if re.match(r"\w", source[-1]):
                pattern = pattern + r"\b"
            entries.append((re.compile(pattern), token, target))
        return entries
