import re
import json
from app.infrastructure.utils.user_context import current_user
from app.infrastructure.utils.enums.migration_event import MigrationEvent
from app.infrastructure.utils.event_helper import MigrationEventHelper

_conversion_event_helper = MigrationEventHelper(
    agent_name="conversion",
    event_name="conversion_started",
)
def _extract_clean_code(raw: str) -> str:
    """
    Extract only executable code from LLM response.
    - If fenced blocks exist, extract and join all fenced code blocks.
    - Strip prose, comments that are outside code, and section headers.
    - Remove leftover markdown artifacts.
    """
    if not raw:
        return ""

    # Extract all fenced code blocks (```...```) and join them
    fenced = re.findall(r"```(?:\w+)?\n(.*?)```", raw, re.DOTALL)
    if fenced:
        return "\n\n".join(block.strip() for block in fenced if block.strip())

    # No fences — strip common markdown prose patterns line by line
    clean_lines = []
    for line in raw.splitlines():
        stripped = line.rstrip()
        # Skip markdown headers, horizontal rules, bold section labels
        if re.match(r"^#{1,6}\s", stripped):
            continue
        if re.match(r"^[-*_]{3,}$", stripped):
            continue
        # Skip lines that are pure prose (no Python syntax indicators)
        # i.e. lines that start with "Note:", "Also,", "This code", etc.
        if re.match(r"^(Note:|Also,|This |Replace |Make sure|Assume|The above)", stripped, re.IGNORECASE):
            continue
        clean_lines.append(line)

    return "\n".join(clean_lines).strip()

def _send_plan_step_progress(step_number: int, plan_id: str) -> None:
    """Emit 20% increments (1→20, 2→40 … 5→100) per plan via workflow event stream."""
    percent = step_number * 20
    try:
        user = current_user.get()
        _conversion_event_helper.send_progress(
            percent=percent,
            message=f"Step {step_number}/5 complete",
            user=user,
            msg_group_id=MigrationEvent.MIGRATION_PROGRESS,
            plan_id=plan_id,
        )
    except Exception:
        pass