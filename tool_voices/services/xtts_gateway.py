from __future__ import annotations

import io
import logging
import os
import sys
from typing import Iterable, Optional, Tuple

# Speed preset configurations for XTTS-v2
# Lower values = faster but potentially lower quality
SPEED_PRESETS = {
    "quality": {"gpt_cond_len": 6, "max_ref_length": 30},
    "balanced": {"gpt_cond_len": 4, "max_ref_length": 20},
    "fast": {"gpt_cond_len": 3, "max_ref_length": 10},
}


class XTTSModelGateway:
    """
    Lazy loader for the XTTS-v2 model shared across services.
    
    Model: tts_models/multilingual/multi-dataset/xtts_v2
    Source: https://huggingface.co/coqui/XTTS-v2
    
    Performance optimizations:
    - GPU auto-detection with CUDA
    - FP16 (half precision) for ~2x speedup on GPU
    - torch.compile for PyTorch 2.0+ optimization
    - Speed presets for quality/speed tradeoffs
    
    Note: XTTS-v2 captures emotion from reference audio during voice cloning,
    not through inference parameters. Emotion is embedded in the voice profile.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        use_gpu: bool = False,
        auto_detect_gpu: bool = True,
        use_fp16: bool = True,
        use_torch_compile: bool = False,
        speed_preset: str = "balanced",
    ) -> None:
        self._model_name = model_name
        self._use_gpu = use_gpu
        self._auto_detect_gpu = auto_detect_gpu
        self._use_fp16 = use_fp16
        self._use_torch_compile = use_torch_compile
        self._speed_preset = speed_preset if speed_preset in SPEED_PRESETS else "balanced"
        self._tts = None
        self._torch = None
        self._logger = logging.getLogger(__name__)
        
        # Resolved GPU state (after auto-detection)
        self._gpu_available = False
        self._gpu_name = ""
        self._fp16_enabled = False
        self._compiled = False

    @property
    def gpu_info(self) -> dict:
        """Get GPU information for UI display."""
        return {
            "available": self._gpu_available,
            "name": self._gpu_name,
            "fp16_enabled": self._fp16_enabled,
            "compiled": self._compiled,
            "speed_preset": self._speed_preset,
        }

    @property
    def torch(self):
        if self._torch is None:
            try:
                import torch  # type: ignore
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
                    self._logger.info(f"GPU detected: {self._gpu_name}")
                else:
                    self._gpu_available = False
                    self._gpu_name = ""
                    self._logger.info("No CUDA GPU detected, using CPU")
        return self._torch

    def _detect_gpu(self) -> bool:
        """Detect if GPU should be used based on settings and availability."""
        torch = self.torch
        
        if self._auto_detect_gpu:
            return torch.cuda.is_available()
        return self._use_gpu and torch.cuda.is_available()

    @property
    def tts(self):
        if self._tts is None:
            # Disable TorchScript JIT to avoid "requires source access" errors
            # in frozen (PyInstaller) builds where some internal kernels
            # don't have an accessible .py source.
            os.environ.setdefault("PYTORCH_JIT", "0")

            torch = self.torch
            try:
                # Best-effort: turn off JIT globally if available.
                if hasattr(torch, "jit") and hasattr(torch.jit, "_state"):
                    try:
                        torch.jit._state.disable()
                    except Exception:
                        pass
            except Exception:
                # If we can't touch JIT state, continue with env flag only.
                pass

            try:
                from TTS.api import TTS  # type: ignore
            except ModuleNotFoundError:
                # Khi chay bang Python binh thuong -> huong dan pip install
                if not getattr(sys, "frozen", False):
                    raise ModuleNotFoundError(
                        "Module 'TTS' chưa được cài đặt.\n"
                        "Vui lòng chạy: pip install TTS"
                    )
                # Khi chay tu file .exe da dong goi ma van thieu TTS -> loi dong goi
                raise RuntimeError(
                    "Ứng dụng thiếu thư viện TTS trong gói build.\n"
                    "Vui lòng sử dụng bản cài đặt mới nhất của Tool Voice Cloning "
                    "hoặc liên hệ người phát triển để rebuild ứng dụng."
                )
            
            # Fix for PyTorch 2.6: patch torch.load to allow loading TTS models
            original_load = torch.load
            
            def patched_load(*args, **kwargs):
                # Set weights_only=False for TTS model loading
                if 'weights_only' not in kwargs:
                    kwargs['weights_only'] = False
                return original_load(*args, **kwargs)
            
            # Add safe globals for XttsConfig if available
            try:
                from TTS.tts.configs.xtts_config import XttsConfig
                if hasattr(torch.serialization, 'add_safe_globals'):
                    torch.serialization.add_safe_globals([XttsConfig])
            except (ImportError, AttributeError):
                pass
            
            # Temporarily patch torch.load
            torch.load = patched_load
            
            # Auto-accept license agreement by patching input() function
            # This allows automatic model download without manual confirmation
            import builtins
            original_input = builtins.input
            
            def auto_accept_input(prompt=""):
                """Auto-accept license agreement by returning 'y' for license prompts."""
                prompt_lower = prompt.lower()
                prompt_text = prompt.strip()
                
                # Check if this is a license confirmation prompt
                # Match various license prompt patterns
                license_keywords = [
                    "commercial license",
                    "non-commercial cpml",
                    "agree to the terms",
                    "coqui",
                    "cpml",
                    "licensing@coqui.ai",
                    "[y/n]",
                    "y/n",
                    "purchased a commercial license",
                    "otherwise, i agree",
                ]
                
                # Also check for prompts that contain license-related text
                is_license_prompt = (
                    any(keyword in prompt_lower for keyword in license_keywords) or
                    "purchased a commercial license" in prompt_lower or
                    "otherwise, i agree" in prompt_lower or
                    ("coqui" in prompt_lower and ("license" in prompt_lower or "cpml" in prompt_lower)) or
                    (len(prompt_text) > 30 and "[y/n]" in prompt_text)
                )
                
                if is_license_prompt:
                    self._logger.info("Tự động chấp nhận license agreement cho XTTS-v2 model")
                    # Print to both stdout and stderr to ensure visibility
                    message = "✓ Tự động chấp nhận license agreement (non-commercial CPML)"
                    print(message, file=sys.stdout)
                    print(message, file=sys.stderr)
                    return "y"
                
                # For other prompts, use original input (though shouldn't happen in this context)
                return original_input(prompt)
            
            # Patch input function
            builtins.input = auto_accept_input
            
            # Determine GPU usage
            use_gpu = self._detect_gpu()
            
            try:
                self._logger.info(f"Loading TTS model: {self._model_name} (GPU: {use_gpu})")
                self._tts = TTS(
                    model_name=self._model_name,
                    progress_bar=False,
                    gpu=use_gpu,
                )
                
                # Apply FP16 optimization if GPU is enabled
                if use_gpu and self._use_fp16:
                    self._apply_fp16()
                
                # Apply torch.compile optimization if enabled
                if self._use_torch_compile:
                    self._apply_torch_compile()
                    
            except Exception as e:
                raise RuntimeError(
                    f"Không thể khởi tạo TTS model '{self._model_name}'.\n"
                    f"Lỗi: {str(e)}\n"
                    "Vui lòng kiểm tra kết nối internet để tải model."
                ) from e
            finally:
                # Restore original functions
                torch.load = original_load
                builtins.input = original_input
        return self._tts

    def _apply_fp16(self) -> None:
        """Apply FP16 (half precision) to model for faster inference on GPU."""
        try:
            if self._tts and hasattr(self._tts, 'synthesizer'):
                tts_model = self._tts.synthesizer.tts_model
                if tts_model is not None:
                    tts_model.half()
                    self._fp16_enabled = True
                    self._logger.info("✅ FP16 (half precision) enabled - ~2x speedup")
        except Exception as e:
            self._logger.warning(f"Could not enable FP16: {e}")
            self._fp16_enabled = False

    def _apply_torch_compile(self) -> None:
        """Apply torch.compile optimization for PyTorch 2.0+."""
        torch = self.torch
        
        # Check PyTorch version
        version_parts = torch.__version__.split('.')
        major_version = int(version_parts[0])
        
        if major_version < 2:
            self._logger.info("torch.compile requires PyTorch 2.0+, skipping")
            return
        
        try:
            if self._tts and hasattr(self._tts, 'synthesizer'):
                tts_model = self._tts.synthesizer.tts_model
                if tts_model is not None and hasattr(torch, 'compile'):
                    # Use reduce-overhead mode for inference
                    tts_model.inference = torch.compile(
                        tts_model.inference, 
                        mode="reduce-overhead",
                        fullgraph=False,  # Allow graph breaks for compatibility
                    )
                    self._compiled = True
                    self._logger.info("✅ torch.compile enabled - 10-30% speedup")
        except Exception as e:
            self._logger.warning(f"Could not apply torch.compile: {e}")
            self._compiled = False

    def get_speed_preset_params(self) -> dict:
        """Get conditioning parameters based on speed preset."""
        return SPEED_PRESETS.get(self._speed_preset, SPEED_PRESETS["balanced"])

    def compute_conditioning_latent(
        self, 
        audio_path: str,
        speed_preset: Optional[str] = None,
    ) -> Tuple[object, object]:
        """Compute conditioning latents with speed preset optimization."""
        tts_model = self.tts.synthesizer.tts_model
        config = tts_model.config
        
        # Use provided preset or instance preset
        preset = speed_preset or self._speed_preset
        preset_params = SPEED_PRESETS.get(preset, SPEED_PRESETS["balanced"])
        
        # Use preset values, falling back to config defaults
        gpt_cond_len = preset_params.get(
            "gpt_cond_len", 
            getattr(config, 'gpt_cond_len', 6)
        )
        max_ref_length = preset_params.get(
            "max_ref_length",
            getattr(config, 'max_ref_len', 30)
        )
        
        self._logger.debug(
            f"Computing conditioning with preset '{preset}': "
            f"gpt_cond_len={gpt_cond_len}, max_ref_length={max_ref_length}"
        )
        
        gpt_cond_latent, speaker_embedding = tts_model.get_conditioning_latents(
            audio_path=audio_path,
            gpt_cond_len=gpt_cond_len,
            max_ref_length=max_ref_length,
            sound_norm_refs=getattr(config, 'sound_norm_refs', False),
        )
        return gpt_cond_latent, speaker_embedding

    def aggregate_conditionings(self, audio_paths: Iterable[str]) -> bytes:
        torch = self.torch
        gpt_latents = []
        speaker_embeddings = []
        for path in audio_paths:
            gpt_latent, speaker_embedding = self.compute_conditioning_latent(path)
            gpt_latents.append(gpt_latent)
            speaker_embeddings.append(speaker_embedding)

        gpt_mean = torch.stack(gpt_latents).mean(dim=0)
        speaker_mean = torch.stack(speaker_embeddings).mean(dim=0)

        buffer = io.BytesIO()
        torch.save(
            {"gpt_latent": gpt_mean.cpu(), "speaker_embedding": speaker_mean.cpu()},
            buffer,
        )
        return buffer.getvalue()

    def reload_model(
        self,
        use_gpu: Optional[bool] = None,
        auto_detect_gpu: Optional[bool] = None,
        use_fp16: Optional[bool] = None,
        use_torch_compile: Optional[bool] = None,
        speed_preset: Optional[str] = None,
    ) -> None:
        """Reload model with new settings."""
        # Update settings
        if use_gpu is not None:
            self._use_gpu = use_gpu
        if auto_detect_gpu is not None:
            self._auto_detect_gpu = auto_detect_gpu
        if use_fp16 is not None:
            self._use_fp16 = use_fp16
        if use_torch_compile is not None:
            self._use_torch_compile = use_torch_compile
        if speed_preset is not None:
            self._speed_preset = speed_preset if speed_preset in SPEED_PRESETS else "balanced"
        
        # Clear current model to force reload
        self._tts = None
        self._fp16_enabled = False
        self._compiled = False
        
        self._logger.info("Model will reload with new settings on next use")
