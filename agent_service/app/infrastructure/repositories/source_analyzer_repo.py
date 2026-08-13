from typing import Dict
from app.infrastructure.utils.http_handler import HttpHandler
from app.domain.interfaces.i_source_analyzer_repo import ISourceAnalyzerRepo
from app.infrastructure.config.settings import settings

class SourceAnalyzerRepo(ISourceAnalyzerRepo):
    """
    Repository to call the external Stack Analyzer API
    """

    def __init__(self):
        # Base URL automatically loaded from .env via Pydantic settings
        self.client = HttpHandler(settings.analyzer_api_url)

    def analyze_source_project(self, source_project_path: str) -> Dict:
        payload = {
            "source_project_path": source_project_path
        }

        return self.client.post("/analyze", data=payload)
