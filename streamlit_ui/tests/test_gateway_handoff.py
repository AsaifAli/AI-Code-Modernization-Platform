from __future__ import annotations

import pytest

from streamlit_ui.gateway_handoff import GatewayHandoffError, _exchange_endpoint, exchange_handoff_code


def test_exchange_endpoint_accepts_gateway_root_or_v1_url() -> None:
    assert _exchange_endpoint("https://gateway.example") == "https://gateway.example/v1/demo/session/exchange"
    assert _exchange_endpoint("https://gateway.example/v1") == "https://gateway.example/v1/demo/session/exchange"


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "https://user:pass@gateway.example",
        "https://gateway.example/path?token=abc",
        "https://gateway.example/path#frag",
        "https:///missing-host",
    ],
)
def test_exchange_endpoint_rejects_unsafe_urls(url: str) -> None:
    with pytest.raises(GatewayHandoffError):
        _exchange_endpoint(url)


@pytest.mark.parametrize("code", ["", "short", "x" * 129, "x" * 40 + " "])
def test_exchange_rejects_invalid_codes_before_network(code: str) -> None:
    with pytest.raises(GatewayHandoffError):
        exchange_handoff_code(code, gateway_url="https://gateway.example")


def test_exchange_requires_gateway_configuration() -> None:
    with pytest.raises(GatewayHandoffError, match="not configured"):
        exchange_handoff_code("a" * 43, gateway_url="")
