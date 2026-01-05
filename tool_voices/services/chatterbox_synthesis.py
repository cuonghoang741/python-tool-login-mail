"""
Voice synthesis service using Chatterbox TTS.
Faster and higher quality than XTTS-v2.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

import numpy as np
import soundfile as sf

from tool_voices.domain import VoiceProfile
from tool_voices.repositories.voice_repository import VoiceRepository
from tool_voices.services.chatterbox_gateway import ChatterboxModelGateway


class ChatterboxSynthesisService:
    """
    Generate speech from text using Chatterbox TTS.
    
    Features:
    - Zero-shot voice cloning from 5s audio
    - <200ms latency (16x faster than XTTS-v2 with vLLM)
    - Emotion exaggeration control
    - 23+ languages supported
    """
    
    _EMOTION_TO_EXAGGERATION: Dict[str, float] = {
        "neutral": 0.3,
        "happy": 0.7,
        "angry": 0.8,
        "sad": 0.6,
        "surprised": 0.9,
        "afraid": 0.7,
    }

    def __init__(
        self,
        gateway: Optional[ChatterboxModelGateway] = None,
        repository: Optional[VoiceRepository] = None,
        output_dir: Optional[Path] = None,
    ) -> None:
        self._gateway = gateway or ChatterboxModelGateway()
        self._repository = repository or VoiceRepository(Path("./voices"))
        self._output_dir: Path = (output_dir or Path("./outputs")).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(__name__)
        self._log_callback: Optional[Callable[[str], None]] = None
    
    def set_log_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Set callback function to receive log messages for UI display."""
        self._log_callback = callback
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log message both to logger and UI callback."""
        # Skip progress messages from file log (too noisy)
        is_progress = "Progress:" in message
        
        if not is_progress:
            if level == "info":
                self._logger.info(message)
            elif level == "warning":
                self._logger.warning(message)
            elif level == "error":
                self._logger.error(message)
            else:
                self._logger.debug(message)
        
        if self._log_callback:
            try:
                self._log_callback(message)
            except Exception:
                pass

    def _load_voice(self, voice_name: str) -> VoiceProfile:
        """Load voice profile from repository."""
        voice = self._repository.load_voice(voice_name)
        if voice is None:
            raise ValueError(f"Không tìm thấy giọng '{voice_name}'.")
        return voice

    def _get_reference_audio(self, voice: VoiceProfile) -> str:
        """Get reference audio path for voice cloning."""
        if voice.samples and len(voice.samples) > 0:
            return str(voice.samples[0])
        raise ValueError(f"Giọng '{voice.name}' không có mẫu âm thanh.")

    def _build_output_path(self, voice_name: str, emotion: str) -> Path:
        """Build output file path."""
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        filename = f"{voice_name}_{emotion}_{timestamp}.wav"
        return self._output_dir / filename

    def _map_emotion_to_exaggeration(self, emotion: str, intensity: float) -> float:
        """Map emotion and intensity to exaggeration value."""
        base = self._EMOTION_TO_EXAGGERATION.get(emotion.lower(), 0.5)
        # Scale by intensity (0.0-1.0)
        return base * intensity

    def synthesize(
        self,
        text: str,
        voice_name: str,
        emotion: str = "neutral",
        intensity: float = 0.5,
        output_path: Optional[Path] = None,
        language_override: Optional[str] = None,
        advanced_params: Optional[Dict[str, object]] = None,
        **kwargs,  # For compatibility with old API
    ) -> Path:
        """
        Synthesize speech from text.
        
        Args:
            text: Text to synthesize
            voice_name: Name of voice profile to use
            emotion: Emotion type (neutral, happy, angry, sad, surprised, afraid)
            intensity: Emotion intensity (0.0 to 1.0)
            output_path: Optional output file path
            language_override: Optional language code (e.g., "en", "vi", "ja")
            advanced_params: Optional advanced parameters
            
        Returns:
            Path to generated audio file
        """
        if not text.strip():
            raise ValueError("Văn bản đầu vào không được để trống.")

        start_time = time.time()
        
        # Load voice profile
        self._log(f"🎤 Đang tải giọng '{voice_name}'...")
        voice = self._load_voice(voice_name)
        reference_audio = self._get_reference_audio(voice)
        self._log(f"✅ Đã tải giọng, sử dụng mẫu: {Path(reference_audio).name}")
        
        # Prepare output path
        destination = output_path or self._build_output_path(voice_name, emotion)
        
        # Map emotion to exaggeration
        exaggeration = self._map_emotion_to_exaggeration(emotion, intensity)
        
        # Get advanced params
        params = advanced_params or {}
        cfg_weight = float(params.get("cfg_weight", 0.5))
        
        self._log(f"⚙️ Parameters: exaggeration={exaggeration:.2f}, cfg_weight={cfg_weight:.2f}")
        self._log(f"📝 Text: {len(text)} ký tự")
        
        # Generate audio
        self._log("🤖 Đang tạo giọng nói với Chatterbox...")
        
        try:
            audio = self._gateway.generate(
                text=text,
                audio_prompt_path=reference_audio,
                exaggeration=exaggeration,
                cfg_weight=cfg_weight,
                language_id=language_override,
                progress_callback=self._log,
            )
        except Exception as e:
            self._log(f"❌ Lỗi sinh giọng: {str(e)}", "error")
            raise
        
        elapsed = time.time() - start_time
        self._log(f"✅ Đã tạo audio trong {elapsed:.2f}s")
        
        # Save audio
        sample_rate = self._gateway.sample_rate
        self._log(f"💾 Đang lưu file ({sample_rate}Hz)...")
        
        # Ensure audio is in correct format
        if audio.dtype != np.float32:
            audio = audio.astype(np.float32)
        
        # Normalize if needed
        max_val = np.abs(audio).max()
        if max_val > 1.0:
            audio = audio / max_val
        
        sf.write(str(destination), audio, sample_rate)
        
        total_time = time.time() - start_time
        self._log(f"✅ Hoàn tất! Tổng thời gian: {total_time:.2f}s")
        self._log(f"📁 File: {destination}")
        
        return destination

    def list_voices(self) -> list:
        """List available voices."""
        voice_names = self._repository.list_voice_names()
        voices = []
        for name in voice_names:
            voice = self._repository.load_voice(name)
            if voice:
                voices.append(voice)
        return voices
