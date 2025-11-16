from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class VoiceProfile:
    name: str
    samples: List[Path] = field(default_factory=list)
    language: str = "auto"
    embedding_path: Optional[Path] = None
    metadata: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, str]:
        data: Dict[str, str] = {
            "name": self.name,
            "language": self.language,
        }
        if self.embedding_path:
            data["embedding_path"] = str(self.embedding_path)
        data.update(self.metadata)
        return data




