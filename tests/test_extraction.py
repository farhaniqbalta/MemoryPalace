from types import SimpleNamespace
from unittest.mock import patch

from app.core.extraction import extract_card


def test_extract_card_returns_tool_input():
    fake_input = {
        "type": "ProblemSolution",
        "title": "Tuya Error 911",
        "content": {
            "problem": "Authentication failed",
            "cause": "Invalid signature",
            "solution": "Regenerate signature",
        },
        "tags": ["Tuya", "API"],
    }
    fake_response = SimpleNamespace(
        content=[SimpleNamespace(type="tool_use", input=fake_input)]
    )

    with patch("app.core.extraction.client.messages.create", return_value=fake_response) as mock_create:
        result = extract_card("some raw text about a Tuya error")

    assert result == fake_input
    args, kwargs = mock_create.call_args
    assert kwargs["tool_choice"] == {"type": "tool", "name": "create_knowledge_card"}
