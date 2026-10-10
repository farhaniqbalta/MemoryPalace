import anthropic

from app.config import settings

client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

_CARD_TOOL = {
    "name": "create_knowledge_card",
    "description": "Create a structured knowledge card from raw text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": (
                    "Card type, e.g. ProblemSolution, Decision, Fact, MeetingNote"
                ),
            },
            "title": {"type": "string"},
            "content": {
                "type": "object",
                "description": (
                    "Type-specific structured fields, e.g. "
                    "{problem, cause, solution} for a ProblemSolution card"
                ),
            },
            "tags": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["type", "title", "content", "tags"],
    },
}

_SYSTEM_PROMPT = (
    "You extract structured knowledge cards from raw text (chat messages, notes, "
    "docs). Choose the card `type` that best fits the content, give it a concise "
    "`title`, capture the substance in `content` as type-appropriate key/value "
    "fields, and add relevant `tags`. Always call create_knowledge_card."
)


def extract_card(raw_text: str) -> dict:
    response = client.messages.create(
        model=settings.claude_model,
        max_tokens=2048,
        system=_SYSTEM_PROMPT,
        tools=[_CARD_TOOL],
        tool_choice={"type": "tool", "name": "create_knowledge_card"},
        messages=[{"role": "user", "content": raw_text}],
    )
    tool_use = next(b for b in response.content if b.type == "tool_use")
    return tool_use.input
