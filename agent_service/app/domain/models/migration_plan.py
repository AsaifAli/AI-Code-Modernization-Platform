from typing import Dict, Any, List

class MigrationPlan:
    """
    Encapsulates a plan for migrating legacy code — e.g. target language, steps, modules to convert.
    """
    def __init__(self, target_language: str, steps: List[str], config: Dict[str, Any]):
        self.target_language = target_language
        self.steps = steps
        self.config = config
