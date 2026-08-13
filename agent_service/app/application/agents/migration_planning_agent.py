class MigrationPlanningAgent:
    """
    (Optional) If you want logic in a separate agent to create migration plans, etc.
    """
    def __init__(self, agent_manager):
        self.agent_manager = agent_manager

    def plan(self, legacy_entity):
        # maybe offload heavy plan logic to agent
        pass
