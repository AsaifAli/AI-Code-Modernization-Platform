from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model
tech_detector = Agent(
    name="Tech Detection Agent",
    model=model,
    markdown=False,
    description=(
        "Generate a list of technologies used in the codebase based on the Stack analyzer data and Project graph. "
    ),
    instructions=[
        "You are an expert software architect and tech stack analyst."
        "Rules-"
        "- libraries: only real external/third-party packages"
        "- Be precise with architecture based on folder structure"
        "- Output ONLY valid JSON, nothing else."      
    ],
)