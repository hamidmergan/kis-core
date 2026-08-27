"""The language is measured separately and put into the prompt, not guessed."""

import pytest

from src.services.openai_compat_llm import _summary as summary_mod
from src.tool_prompts import SUMMARY_DEFAULT


COVER = (
    "Technische Hochschule Luebeck\n"
    "Fachbereich Elektrotechnik und Informatik\n"
    "Vorlesungsskript zum Modul Verteilte Systeme\n"
    "Sommersemester 2026\n"
)
BODY = (
    "A distributed system is a collection of independent computers that appears "
    "to its users as a single coherent system. The machines communicate only by "
    "passing messages over a network. There is no shared memory and no global "
    "clock. Concurrency is the first challenge, because multiple components "
    "execute at the same time and may access the same resources. Partial failure "
    "is the second challenge, because one node may fail while the others keep "
    "running. Consistency is the third challenge, because replicas can diverge "
    "when data is spread over several nodes. Replication improves availability "
    "and read throughput, consensus protocols let a group of nodes agree on a "
    "single value, and sharding splits a large dataset across many nodes. "
) * 3
FOOTER = "\nSeite 1 von 12\nTechnische Hochschule Luebeck, Moenkhofer Weg 239\n"
MIXED_DOC = COVER + BODY + FOOTER


class _Message:
    def __init__(self, content):
        self.content = content


class _Choice:
    def __init__(self, content):
        self.message = _Message(content)


class _Response:
    def __init__(self, content):
        self.choices = [_Choice(content)]


class _FakeCompletions:
    def __init__(self, owner):
        self._owner = owner

    def create(self, **kwargs):
        self._owner.calls.append(kwargs)
        reply = self._owner.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return _Response(reply)


class _FakeOpenAI:
    """Records every chat.completions.create call and replays canned replies."""

    def __init__(self, replies):
        self.replies = list(replies)
        self.calls = []
        self.chat = type("_Chat", (), {"completions": _FakeCompletions(self)})()


class _Client(summary_mod._SummaryMixin):
    def __init__(self, replies):
        self._client = _FakeOpenAI(replies)
        self._model = "chat-fast"


def _system_of(call):
    return next(m["content"] for m in call["messages"] if m["role"] == "system")


def _user_of(call):
    return next(m["content"] for m in call["messages"] if m["role"] == "user")


# -- language sampling --------------------------------------------------------


def test_language_sample_skips_cover_page_and_footer():
    """The probe must not see the edges, that is where the boilerplate lives."""
    sample = summary_mod._language_sample(MIXED_DOC)

    assert "Vorlesungsskript" not in sample
    assert "Moenkhofer Weg" not in sample
    assert "distributed system" in sample


def test_language_sample_returns_short_text_unchanged():
    short = "A very short document about nothing in particular."
    assert summary_mod._language_sample(short) == short


# -- language pinning ---------------------------------------------------------


def test_detected_language_is_pinned_into_the_prompt():
    client = _Client(["English", "the summary"])

    client.generate_summary(MIXED_DOC)

    probe, summary = client._client.calls
    assert "distributed system" in _user_of(probe)
    system = _system_of(summary)
    assert "English" in system
    # The model must not be asked to decide the language for itself again.
    assert "dominant language" not in system


def test_probe_answer_is_sanitized_before_it_reaches_the_prompt():
    """A chatty probe answer must not be pasted into the prompt verbatim."""
    client = _Client(["Sure! The dominant language of this text is English.", "the summary"])

    client.generate_summary(MIXED_DOC)

    system = _system_of(client._client.calls[1])
    assert "Sure!" not in system


@pytest.mark.parametrize("bad", [RuntimeError("boom"), "", None])
def test_summary_survives_a_failed_language_probe(bad):
    client = _Client([bad, "the summary"])

    assert client.generate_summary(MIXED_DOC) == "the summary"
    assert len(client._client.calls) == 2


# -- output format ------------------------------------------------------------


def test_only_plain_text_is_produced():
    """Markdown and HTML are gone, the tool always returns plain text."""
    assert "{format}" not in SUMMARY_DEFAULT

    client = _Client(["English", "the summary"])
    client.generate_summary(MIXED_DOC)

    system = _system_of(client._client.calls[1])
    assert "No Markdown, no HTML" in system

    # generate_summary takes the text only, there is no format to pass any more.
    with pytest.raises(TypeError):
        client.generate_summary(MIXED_DOC, output_format="md")


def test_prompt_carries_no_german_instruction_text():
    """German instruction text inside the prompt would bias the output language."""
    assert "Zusammenfassung" not in SUMMARY_DEFAULT


# -- register -----------------------------------------------------------------


def test_prompt_has_no_lecturer_persona():
    lowered = SUMMARY_DEFAULT.lower()
    for phrase in ("lecturer", "spoken summary", "address the audience"):
        assert phrase not in lowered
