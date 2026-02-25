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
    reviewers: list[str] = field(default_factory=list)
    metadata: dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> dict:
        """Convert to dictionary for CSV/JSON output, including metadata."""
        data = asdict(self)
        # Flatten metadata back into the main dict
        meta = data.pop("metadata", {})
        data.update(meta)
        # Convert reviewers list to comma-separated string for CSV
        data["reviewers"] = ", ".join(self.reviewers)
        return data


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


class PRPairingError(Exception):
    """Base exception for PR pairing tool."""
    pass


class CSVValidationError(PRPairingError):
    """CSV validation failed."""
    pass


class FileError(PRPairingError):
    """File operation failed."""
    pass
