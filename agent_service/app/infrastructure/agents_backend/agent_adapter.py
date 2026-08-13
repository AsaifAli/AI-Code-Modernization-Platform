from typing import Any, Dict
import json
class AgentAdapter:
    """
    Utility adapter to transform between internal domain data and agent messages,
    or parse agent output into structured internal objects.
    """

    @staticmethod
    def format_tool_call(tool_name: str, *args, **kwargs) -> str:
        """
        Format a string or JSON message that your agent can understand for invoking a tool.
        """
        data = {
            "tool": tool_name,
            "args": args,
            "kwargs": kwargs,
        }
        return json.dumps(data)

    @staticmethod
    def parse_response(resp: Any) -> Any:
        """
        Parse the raw response returned by the agent into a domain object or type.
        """
        # If response is JSON-like string, try to parse it
        try:
            import json
            return json.loads(resp)
        except Exception:
            return resp
