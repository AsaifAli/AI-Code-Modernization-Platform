from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model
from app.application.agents.chat.chat_tools import ask_kb


chat_agent = Agent(
    name="KB Chat Agent",
    model=model,
    markdown=True,
    use_json_mode=False,
    instructions=(
        "Answer user questions using the KB search tool. "
        "Never request or require full syntactic AST in the prompt context. "
        "Prefer file-scoped KB retrieval when a file path is provided."
    ),
    tools=[ask_kb],
    debug_mode=True,
    description="Chat assistant backed by KB chunk retrieval.",
)

