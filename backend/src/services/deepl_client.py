import deepl


class DeepLClient:
    def __init__(self, api_key: str):
        self._translator = deepl.Translator(api_key)

    @property
    def raw(self) -> deepl.Translator:
        """Direct access to the underlying deepl.Translator for Document API."""
        return self._translator

    def translate_text(self, text: str, source_lang: str, target_lang: str) -> str:
        result = self._translator.translate_text(
            text, source_lang=source_lang, target_lang=target_lang
        )
        return result.text
