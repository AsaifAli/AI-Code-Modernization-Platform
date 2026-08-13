from abc import ABC, abstractmethod
from typing import Dict


class ISourceAnalyzerRepo(ABC):
    """
    Interface for calling Source Analyzer REST API.
    """

    @abstractmethod
    def analyze_source_project(self, source_project_path: str) -> Dict:
        pass
