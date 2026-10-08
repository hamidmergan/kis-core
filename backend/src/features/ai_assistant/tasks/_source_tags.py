"""Short stand-ins for file names in a prompt, the answer gets the real names back.

A file name costs the model up to 25 tokens every time it writes it, and a mind map
names its file at every node. Measured 08.10.2026 on gemma4:31b via Ollama: half of
a deepening answer was file names, with stand-ins it wrote the same 18 nodes on the
same pages in 26 s instead of 32 s.
"""

from __future__ import annotations


class SourceTags:
    """Maps every file name to Q1, Q2, ... and back."""

    def __init__(self, labels):
        names = list(dict.fromkeys(l for l in labels if l))
        self._to_tag = {name: f"Q{i}" for i, name in enumerate(names, 1)}
        self._to_name = {tag: name for name, tag in self._to_tag.items()}
        # Longest first, so a name that sits inside another one is not replaced in it.
        self._order = sorted(self._to_tag, key=len, reverse=True)

    def encode_text(self, text: str) -> str:
        """The text with every file name replaced by its tag."""
        for name in self._order:
            text = text.replace(name, self._to_tag[name])
        return text

    def encode(self, messages: list[dict]) -> list[dict]:
        """The messages as the model gets them."""
        # No legend with the real names: the model copied them from it and made one up.
        return [{**m, "content": self.encode_text(m["content"])}
                if isinstance(m.get("content"), str) else m for m in messages]

    def decode(self, data):
        """Every source_label in the answer back to the file name, an unknown one stays as it is."""
        if isinstance(data, dict):
            out = {k: self.decode(v) for k, v in data.items()}
            label = out.get("source_label")
            if isinstance(label, str):
                out["source_label"] = self._to_name.get(label.strip(), label)
            return out
        if isinstance(data, list):
            return [self.decode(v) for v in data]
        return data
