class AgentManager:
    """
    Manages lifecycle, configuration, and injection of agents (scanner, converter, etc.)
    """

    def __init__(self, connector):
        self.connector = connector

    def call_tool(self, tool_name: str, *args, **kwargs):
        return self.connector.call_tool(tool_name, *args, **kwargs)
