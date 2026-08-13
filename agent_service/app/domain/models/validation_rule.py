from abc import ABC, abstractmethod
from app.domain.models.legacy_code_entity import LegacyCodeEntity


class ValidationRule(ABC):
    """
    Abstract base class for all validation rules.
    Each rule must define:
      - name: unique rule identifier
      - severity: "error" or "warning"
      - validate(entity): returns True (pass) or False (fail)
    """

    def __init__(self, name: str, severity: str = "error"):
        self.name = name
        self.severity = severity

    @abstractmethod
    def validate(self, legacy_entity: LegacyCodeEntity) -> bool:
        """
        Validate the given legacy entity.
        Returns True if rule passes, False otherwise.
        """
        pass
