from abc import ABC, abstractmethod
from typing import List

class Prompt(ABC):
    
    @abstractmethod
    def getTechnicalDocumentationPrompt(respDetectedTechGraph: str) -> str:
        pass
    
    @abstractmethod
    def getFunctionalDocumentationPrompt(respDetectedTechGraph: str) -> str:
        pass
    
    @abstractmethod
    def getEnhancedScannerResponsePrompt(respDetectedTechGraph: str) -> str:
        pass
    
    @abstractmethod
    def getPumlPrompt(semantic_ir: List, tech_data: dict, dep_graph: dict,) -> str:
        pass