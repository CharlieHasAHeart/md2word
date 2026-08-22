import pytest


@pytest.fixture(autouse=True)
def disable_formalizer_llm_env(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("MD2WORD_LLM_BASE_URL", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_API_KEY", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_MODEL", raising=False)
    monkeypatch.delenv("MD2WORD_LLM_CLEANER_TIMEOUT", raising=False)
