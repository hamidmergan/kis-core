"""No hard-wired closing remark on the last script."""

from src.services.openai_compat_llm._scripts import _ScriptsMixin


class FakeMessage:
    def __init__(self, content):
        self.content = content


class FakeChoice:
    def __init__(self, content):
        self.message = FakeMessage(content)
        self.finish_reason = "stop"


class FakeResponse:
    def __init__(self, content):
        self.choices = [FakeChoice(content)]


class FakeCompletions:
    def __init__(self, replies):
        self._replies = list(replies)
        self.calls: list[list[dict]] = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        return FakeResponse(self._replies.pop(0) if self._replies else "...")


class FakeClient:
    def __init__(self, replies):
        self.chat = type("Chat", (), {"completions": FakeCompletions(replies)})()


class ScriptClient(_ScriptsMixin):
    def __init__(self, replies, batch_size=3):
        self._client = FakeClient(replies)
        self._model = "test-model"
        self._extra_body = {}
        self._batch_size = batch_size
        self._batch_max_workers = 1
        self._batch_timeout = 5.0

    @property
    def calls(self):
        return self._client.chat.completions.calls


def _slides(n: int) -> list[str]:
    return [f"Folientext {i + 1}" for i in range(n)]


def test_kein_englischer_dank_bei_add_closing():
    client = ScriptClient(["Skript A\n|||\nSkript B\n|||\nSkript C"])
    scripts = client.generate_scripts_batch(
        _slides(3), add_greeting=False, add_closing=True, target_lang="DE"
    )
    assert scripts == ["Skript A", "Skript B", "Skript C"]
    assert not any("thank you" in s.lower() for s in scripts)


def test_add_closing_false_verbietet_die_floskel_im_prompt():
    client = ScriptClient(["Skript A\n|||\nSkript B\n|||\nSkript C"])
    client.generate_scripts_batch(
        _slides(3), add_greeting=False, add_closing=False, target_lang="DE"
    )
    system_prompt = client.calls[0][0]["content"]
    assert "Do not add any closing statement or thank-you." in system_prompt
