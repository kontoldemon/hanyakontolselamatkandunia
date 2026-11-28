from cloudsentinel.threat_reporter import _litellm_connection_kwargs


def test_litellm_connection_kwargs_empty(monkeypatch) -> None:
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_ENDPOINT", raising=False)
    assert _litellm_connection_kwargs() == {}


def test_litellm_connection_kwargs_opencode(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "unit-key")
    monkeypatch.setenv(
        "LLM_ENDPOINT",
        "https://opencode.ai/inference/go/openai/v1",
    )
    kwargs = _litellm_connection_kwargs()
    assert kwargs["api_key"] == "unit-key"
    assert kwargs["api_base"] == "https://opencode.ai/inference/go/openai/v1"
    assert kwargs["extra_headers"]["x-opencode-session"] == "cloudsentinel-sensor"


def test_litellm_connection_kwargs_other_provider(monkeypatch) -> None:
    monkeypatch.setenv("LLM_API_KEY", "unit-key")
    monkeypatch.setenv("LLM_ENDPOINT", "https://api.deepseek.com")
    kwargs = _litellm_connection_kwargs()
    assert kwargs["api_key"] == "unit-key"
    assert "extra_headers" not in kwargs
