from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Iterable, List, Optional

from tool_voices.domain import VoiceProfile
from tool_voices.repositories.voice_repository import VoiceRepository
from tool_voices.services.xtts_gateway import XTTSModelGateway


class VoiceCloneService:
    """Handle voice sample ingestion and XTTS conditioning extraction."""

    def __init__(
        self,
        repository: Optional[VoiceRepository] = None,
        gateway: Optional[XTTSModelGateway] = None,
    ) -> None:
        self._repository = repository or VoiceRepository(Path("./voices"))
        self._gateway = gateway or XTTSModelGateway()
        self._logger = logging.getLogger(__name__)

    def create_voice_profile(
        self,
        voice_name: str,
        sample_paths: Iterable[Path],
        language: str = "auto",
    ) -> VoiceProfile:
        """Create voice profile by simply saving audio files - no training required."""
        samples = list(sample_paths)
        if not voice_name:
            raise ValueError("voice_name is required")
        if not samples:
            raise ValueError("At least one sample file is required")
        if self._repository.load_voice(voice_name):
            raise ValueError(f"Voice '{voice_name}' already exists. Vui lòng chọn tên khác.")

        self._logger.info("Saving voice profile '%s' with %d samples (no training needed).", voice_name, len(samples))
        
        # Simply save the profile with audio files - conditioning will be computed on-the-fly during synthesis
        profile = VoiceProfile(name=voice_name, language=language)
        profile.metadata["created_at"] = datetime.utcnow().isoformat()
        profile.metadata["sample_count"] = str(len(samples))
        profile.metadata["mode"] = "direct"  # Mark as direct mode (no pre-computed embeddings)

        # Save without embedding data - will compute on demand
        saved_profile = self._repository.save_voice(profile, samples, embedding_data=None)
        self._logger.info("Voice '%s' saved successfully (ready for immediate use).", voice_name)
        return saved_profile

    def list_available_voices(self) -> List[str]:
        return self._repository.list_voice_names()

    def get_voice(self, name: str) -> Optional[VoiceProfile]:
        return self._repository.load_voice(name)
    
    def delete_voice(self, name: str) -> bool:
        """Delete a voice profile."""
        return self._repository.delete_voice(name)