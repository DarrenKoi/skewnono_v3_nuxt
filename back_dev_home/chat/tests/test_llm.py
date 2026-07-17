import httpx
import pytest

from back_dev_home.chat import llm


class _FakeResp:
    def __init__(self, status_code, payload=None, text=""):
        self.status_code = status_code
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


def test_send_chat_success(monkeypatch):
    payload = {
        "choices": [{"message": {"content": "hi there"}}],
        "usage": {"prompt_tokens": 5, "completion_tokens": 2},
    }
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp(200, payload))
    out = llm.send_chat("m", [{"role": "user", "content": "hi"}])
    assert out["content"] == "hi there"
    assert out["prompt_tokens"] == 5
    assert out["completion_tokens"] == 2
    assert isinstance(out["latency_ms"], int)


def test_send_chat_timeout_raises(monkeypatch):
    def _boom(*a, **k):
        raise httpx.TimeoutException("slow")
    monkeypatch.setattr(httpx, "post", _boom)
    with pytest.raises(llm.ChatTimeout):
        llm.send_chat("m", [])


def test_send_chat_error_status_raises(monkeypatch):
    monkeypatch.setattr(httpx, "post", lambda *a, **k: _FakeResp(500, text="boom"))
    with pytest.raises(llm.ChatUpstreamError):
        llm.send_chat("m", [])
