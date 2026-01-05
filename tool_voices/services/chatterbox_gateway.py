"""
Gateway for Chatterbox TTS model.
Replaces XTTS-v2 with faster, higher quality Chatterbox.
"""
from __future__ import annotations

import io
import logging
import os
from pathlib import Path
from typing import Optional, Tuple

import numpy as np


class ChatterboxModelGateway:
    """
    Lazy loader for the Chatterbox TTS model.
    
    Features:
    - Zero-shot voice cloning from 5s audio
    - <200ms latency
    - Emotion exaggeration control
    - 23+ languages supported
    
    Source: https://github.com/resemble-ai/chatterbox
    """

    def __init__(
        self,
        use_gpu: bool = True,
        auto_detect_gpu: bool = True,
        model_type: str = "standard",  # "standard", "turbo" (English only), "multilingual"
    ) -> None:
        self._use_gpu = use_gpu
        self._auto_detect_gpu = auto_detect_gpu
        self._model_type = model_type
        self._model = None
        self._torch = None
        self._logger = logging.getLogger(__name__)
        
        # Resolved state
        self._gpu_available = False
        self._gpu_name = ""
        self._device = "cpu"

    @property
    def gpu_info(self) -> dict:
        """Get GPU information for UI display."""
        return {
            "available": self._gpu_available,
            "name": self._gpu_name,
            "device": self._device,
            "model_type": self._model_type,
        }

    @property
    def torch(self):
        if self._torch is None:
            try:
                import torch
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "Module 'torch' chưa được cài đặt.\n"
                    "Vui lòng chạy: pip install torch"
                )
            self._torch = torch
            
            # Check GPU availability
            if self._auto_detect_gpu or self._use_gpu:
                if torch.cuda.is_available():
                    self._gpu_available = True
                    self._gpu_name = torch.cuda.get_device_name(0)
                    self._device = "cuda"
                    self._logger.info(f"GPU detected: {self._gpu_name}")
                else:
                    self._gpu_available = False
                    self._device = "cpu"
                    self._logger.info("No CUDA GPU detected, using CPU")
        return self._torch

    def _detect_device(self) -> str:
        """Detect and return the appropriate device."""
        torch = self.torch
        if self._auto_detect_gpu and torch.cuda.is_available():
            return "cuda"
        elif self._use_gpu and torch.cuda.is_available():
            return "cuda"
        return "cpu"

    @property
    def model(self):
        """Lazily load the Chatterbox model."""
        if self._model is None:
            device = self._detect_device()
            self._device = device
            
            self._logger.info(f"Loading Chatterbox model (type={self._model_type}, device={device})...")
            
            try:
                if self._model_type == "turbo":
                    from chatterbox.tts_turbo import ChatterboxTurboTTS
                    self._model = ChatterboxTurboTTS.from_pretrained(device=device)
                    self._logger.info("✅ Chatterbox Turbo loaded - fastest inference")
                elif self._model_type == "multilingual":
                    from chatterbox.mtl_tts import ChatterboxMultilingualTTS
                    self._model = ChatterboxMultilingualTTS.from_pretrained(device=device)
                    self._logger.info("✅ Chatterbox Multilingual loaded - 23 languages")
                else:
                    from chatterbox.tts import ChatterboxTTS
                    self._model = ChatterboxTTS.from_pretrained(device=device)
                    self._logger.info("✅ Chatterbox Standard loaded")
                    
            except Exception as e:
                raise RuntimeError(
                    f"Không thể khởi tạo Chatterbox model.\n"
                    f"Lỗi: {str(e)}\n"
                    "Vui lòng kiểm tra kết nối internet để tải model."
                ) from e
                
        return self._model

    @property
    def sample_rate(self) -> int:
        """Get the model's sample rate."""
        return self.model.sr

    def generate(
        self,
        text: str,
        audio_prompt_path: Optional[str] = None,
        exaggeration: float = 0.5,
        cfg_weight: float = 0.5,
        language_id: Optional[str] = None,
        progress_callback: Optional[callable] = None,
    ) -> np.ndarray:
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize
            audio_prompt_path: Path to reference audio for voice cloning
            exaggeration: Emotion exaggeration (0.0 = monotone, 1.0 = expressive)
            cfg_weight: Classifier-free guidance weight
            language_id: Language code for multilingual model (e.g., "en", "vi", "ja")
            progress_callback: Optional callback for progress updates
            
        Returns:
            Audio waveform as numpy array
        """
        import sys
        import io
        import threading
        import time
        
        model = self.model
        
        # Build generation kwargs
        kwargs = {"text": text}
        
        if audio_prompt_path:
            kwargs["audio_prompt_path"] = audio_prompt_path
            
        # Add exaggeration for emotion control (Turbo model supports this)
        if hasattr(model, 'generate') and self._model_type == "turbo":
            kwargs["exaggeration"] = exaggeration
            kwargs["cfg_weight"] = cfg_weight
            
        # Add language for multilingual model
        if language_id and self._model_type == "multilingual":
            kwargs["language_id"] = language_id
            
        self._logger.debug(f"Generating speech: {kwargs}")
        
        # Set up progress capturing
        wav = None
        error = None
        
        if progress_callback:
            # Capture stderr to get tqdm progress
            import re
            
            class TqdmCapture:
                def __init__(self, original, callback):
                    self.original = original
                    self.callback = callback
                    self.buffer = ""
                    
                def write(self, text):
                    # Don't write to terminal - only capture for UI
                    self.buffer += text
                    
                    # Parse tqdm progress: "14%|███| 143/1000 [00:19<02:11, 6.54it/s]"
                    match = re.search(r'(\d+)%\|[^|]*\|\s*(\d+)/(\d+)\s*\[([^\]]+)\]', self.buffer)
                    if match:
                        percent = int(match.group(1))
                        current = int(match.group(2))
                        total = int(match.group(3))
                        timing = match.group(4)
                        self.callback(f"🔄 Progress: {percent}% ({current}/{total}) [{timing}]")
                        self.buffer = ""
                        
                def flush(self):
                    pass  # Don't flush to terminal
            
            original_stderr = sys.stderr
            sys.stderr = TqdmCapture(original_stderr, progress_callback)
            
            try:
                wav = model.generate(**kwargs)
            finally:
                sys.stderr = original_stderr
        else:
            wav = model.generate(**kwargs)
        
        # Convert to numpy if needed
        if hasattr(wav, 'cpu'):
            wav = wav.cpu()
        if hasattr(wav, 'numpy'):
            wav = wav.numpy()
        if len(wav.shape) > 1:
            wav = wav.squeeze()
            
        return wav.astype(np.float32)

    def reload_model(
        self,
        use_gpu: Optional[bool] = None,
        auto_detect_gpu: Optional[bool] = None,
        model_type: Optional[str] = None,
    ) -> None:
        """Reload model with new settings."""
        if use_gpu is not None:
            self._use_gpu = use_gpu
        if auto_detect_gpu is not None:
            self._auto_detect_gpu = auto_detect_gpu
        if model_type is not None:
            self._model_type = model_type
            
        # Clear model to force reload
        self._model = None
        self._logger.info("Model will reload with new settings on next use")
