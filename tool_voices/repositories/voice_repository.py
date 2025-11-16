from __future__ import annotations

import json
import shutil
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional

from tool_voices.domain import VoiceProfile


@dataclass
class VoiceRepository:
    root_dir: Path
    _logger: logging.Logger = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._logger = logging.getLogger(__name__)
        self.root_dir.mkdir(parents=True, exist_ok=True)

    def list_voice_names(self) -> List[str]:
        voices = sorted(
            [
                path.name
                for path in self.root_dir.iterdir()
                if path.is_dir() and (path / "voice.json").exists()
            ]
        )
        self._logger.debug("Voice inventory: %s", voices)
        return voices

    def load_voice(self, name: str) -> Optional[VoiceProfile]:
        voice_dir = self.root_dir / name
        meta_file = voice_dir / "voice.json"
        if not meta_file.exists():
            self._logger.debug("Voice '%s' not found in repository.", name)
            return None
        with meta_file.open("r", encoding="utf-8") as handle:
            data: Dict[str, str] = json.load(handle)
        samples_dir = voice_dir / "samples"
        samples = sorted(samples_dir.glob("*")) if samples_dir.exists() else []
        embedding = (
            Path(data["embedding_path"]) if data.get("embedding_path") else None
        )
        metadata = {k: v for k, v in data.items() if k not in {"name", "language", "embedding_path"}}
        return VoiceProfile(
            name=data.get("name", name),
            language=data.get("language", "auto"),
            samples=list(samples),
            embedding_path=embedding,
            metadata=metadata,
        )

    def save_voice(
        self,
        profile: VoiceProfile,
        samples: Iterable[Path],
        embedding_data: Optional[bytes] = None,
    ) -> VoiceProfile:
        voice_dir = self.root_dir / profile.name
        samples_dir = voice_dir / "samples"
        samples_dir.mkdir(parents=True, exist_ok=True)

        stored_samples: List[Path] = []
        for path in samples:
            destination = samples_dir / path.name
            shutil.copy2(path, destination)
            stored_samples.append(destination)

        embedding_path: Optional[Path] = None
        if embedding_data:
            embedding_path = voice_dir / "speaker_embedding.bin"
            with embedding_path.open("wb") as handle:
                handle.write(embedding_data)

        profile.samples = stored_samples
        profile.embedding_path = embedding_path

        meta_file = voice_dir / "voice.json"
        with meta_file.open("w", encoding="utf-8") as handle:
            json.dump(
                {
                    **profile.to_dict(),
                    "samples": [str(sample) for sample in profile.samples],
                },
                handle,
                indent=2,
                ensure_ascii=False,
            )
        self._logger.info(
            "Voice '%s' persisted with %d samples.",
            profile.name,
            len(profile.samples),
        )
        return profile

    def delete_voice(self, name: str) -> bool:
        """Delete a voice profile and all its associated files."""
        voice_dir = self.root_dir / name
        if not voice_dir.exists():
            self._logger.warning("Voice '%s' not found for deletion.", name)
            return False
        
        try:
            shutil.rmtree(voice_dir)
            self._logger.info("Voice '%s' deleted successfully.", name)
            return True
        except Exception as e:
            self._logger.error("Failed to delete voice '%s': %s", name, e)
            return False

