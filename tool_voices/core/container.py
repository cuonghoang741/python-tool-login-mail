from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from tool_voices.core.config import ConfigManager
from tool_voices.repositories.voice_repository import VoiceRepository
from tool_voices.services.voice_clone import VoiceCloneService
from tool_voices.services.voice_synthesis import VoiceSynthesisService
from tool_voices.services.xtts_gateway import XTTSModelGateway


@dataclass
class ServiceContainer:
    """Simple dependency container wiring application services."""

    _config_manager: Optional[ConfigManager] = field(default=None, init=False)
    _voice_repository: Optional[VoiceRepository] = field(default=None, init=False)
    _xtts_gateway: Optional[XTTSModelGateway] = field(default=None, init=False)
    _voice_clone_service: Optional[VoiceCloneService] = field(default=None, init=False)
    _voice_synthesis_service: Optional[VoiceSynthesisService] = field(default=None, init=False)

    @property
    def config_manager(self) -> ConfigManager:
        if self._config_manager is None:
            self._config_manager = ConfigManager(Path.cwd())
        return self._config_manager

    @property
    def voice_repository(self) -> VoiceRepository:
        if self._voice_repository is None:
            self._voice_repository = VoiceRepository(self.config_manager.voices_dir)
        return self._voice_repository

    @property
    def xtts_gateway(self) -> XTTSModelGateway:
        if self._xtts_gateway is None:
            config = self.config_manager.config
            self._xtts_gateway = XTTSModelGateway(
                model_name=self.config_manager.model_id,
                use_gpu=config.use_gpu,
                auto_detect_gpu=config.auto_detect_gpu,
                use_fp16=config.use_fp16,
                use_torch_compile=config.use_torch_compile,
                speed_preset=config.speed_preset,
            )
        return self._xtts_gateway

    @property
    def voice_clone_service(self) -> VoiceCloneService:
        if self._voice_clone_service is None:
            self._voice_clone_service = VoiceCloneService(
                repository=self.voice_repository,
                gateway=self.xtts_gateway,
            )
        return self._voice_clone_service

    @property
    def voice_synthesis_service(self) -> VoiceSynthesisService:
        if self._voice_synthesis_service is None:
            self._voice_synthesis_service = VoiceSynthesisService(
                voice_clone_service=self.voice_clone_service,
                gateway=self.xtts_gateway,
                repository=self.voice_repository,
                output_dir=self.config_manager.outputs_dir,
            )
        return self._voice_synthesis_service

