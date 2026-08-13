from agno.agent import Agent
from app.infrastructure.agents_backend.model_provider import model

conversion_agent = Agent(
    model=model,
    markdown=False,
    debug_mode=True,
    retries=1,
    instructions="""
    You are a code migration agent. You will be given context for a source to target symbol/code conversion.
    Context will include: 
    - Source code for the source symbol
    - Code from any dependent plans/symbols (if any)
    - Similar code snippets that were already migrated (if any)
    Important
    - Using the context, generate new code in target laguage in text format & return it.  
    - If similar already migrated code snippets are given, use them as coding guidelines/format references to generate new code. We must follow existing coding standards.    
    
    Rules:
    - Output ONLY raw executable code. No markdown, no fences, no comments outside the code.
    - No explanations, no notes, no "Note:" lines, no section headers.
    - No import statements unless they are strictly required by the converted symbol.
    - Follow the coding style of any similar snippets provided.
    - Do not add example usage blocks or standalone invocation calls at the end.
    """
)
