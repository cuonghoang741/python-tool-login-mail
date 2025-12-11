from __future__ import annotations

from datetime import datetime
import logging
from pathlib import Path
from typing import Callable, Iterable, List, Optional

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
        progress_callback: Optional[Callable[[str], None]] = None,
    ) -> VoiceProfile:
        """
        Create a voice profile and precompute conditioning so future synth is instant.
        
        - Copy samples into repository
        - Precompute XTTS conditioning (gpt_latent + speaker_embedding)
        - Persist embedding so workers don't recompute on first use
        """
        samples = list(sample_paths)
        if not voice_name:
            raise ValueError("voice_name is required")
        if not samples:
            raise ValueError("At least one sample file is required")
        if self._repository.load_voice(voice_name):
            raise ValueError(f"Voice '{voice_name}' already exists. Vui lòng chọn tên khác.")

        def _notify(message: str) -> None:
            if progress_callback:
                try:
                    progress_callback(message)
                except Exception:
                    pass
            self._logger.info(message)

        _notify(f"🔍 Kiểm tra giọng '{voice_name}' và mẫu...")
        self._logger.info(
            "Saving voice profile '%s' with %d samples (precomputing conditioning).",
            voice_name,
            len(samples),
        )

        # Precompute conditioning to avoid first-request latency
        try:
            _notify("🎛️ Đang tính conditioning latents...")
            embedding_data = self._gateway.aggregate_conditionings([str(p) for p in samples])
            _notify("✅ Đã tính conditioning latents.")
        except Exception as exc:  # noqa: BLE001
            self._logger.error("Failed to compute conditioning for '%s': %s", voice_name, exc)
            raise

        profile = VoiceProfile(name=voice_name, language=language)
        profile.metadata["created_at"] = datetime.utcnow().isoformat()
        profile.metadata["sample_count"] = str(len(samples))
        profile.metadata["mode"] = "precomputed"
        profile.metadata["status"] = "ready"
        profile.metadata["prepared_at"] = datetime.utcnow().isoformat()

        _notify("💾 Đang lưu giọng và embedding...")
        saved_profile = self._repository.save_voice(profile, samples, embedding_data=embedding_data)
        _notify("🎉 Voice sẵn sàng sử dụng.")
        return saved_profile

    def list_available_voices(self) -> List[str]:
        return self._repository.list_voice_names()

    def get_voice(self, name: str) -> Optional[VoiceProfile]:
        return self._repository.load_voice(name)
    
    def delete_voice(self, name: str) -> bool:
        """Delete a voice profile."""
        return self._repository.delete_voice(name)