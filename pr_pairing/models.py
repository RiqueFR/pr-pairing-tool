from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Optional, TypedDict


DEFAULT_KNOWLEDGE_LEVEL = 3
EXPERT_MIN_LEVEL = 4
NOVICE_MAX_LEVEL = 2


class KnowledgeMode(Enum):
    ANYONE = "anyone"
    EXPERTS_ONLY = "experts-only"
    MENTORSHIP = "mentorship"
    SIMILAR_LEVELS = "similar-levels"


@dataclass
class Developer:
    name: str
    can_review: bool
    team: str = ""
    knowledge_level: int = DEFAULT_KNOWLEDGE_LEVEL
    
    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class History:
    pairs: dict[str, dict[str, int]] = field(default_factory=dict)
    last_run: Optional[str] = None
    
    @staticmethod
    def from_dict(data: dict) -> "History":
        return History(
            pairs=data.get("pairs", {}),
            last_run=data.get("last_run")
        )
    
    def to_dict(self) -> dict:
        return {
            "pairs": self.pairs,
            "last_run": self.last_run
        }


class ReviewerCandidate(TypedDict):
    name: str
    team: str
    knowledge_level: int


class PRPairingError(Exception):
    """Base exception for PR pairing tool."""
    pass


class CSVValidationError(PRPairingError):
    """CSV validation failed."""
    pass


class FileError(PRPairingError):
    """File operation failed."""
    pass
