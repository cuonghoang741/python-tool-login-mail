from __future__ import annotations

import io
import os
import sys
from typing import Iterable, Optional, Tuple


class XTTSModelGateway:
    """
    Lazy loader for the XTTS-v2 model shared across services.
    
    Model: tts_models/multilingual/multi-dataset/xtts_v2
    Source: https://huggingface.co/coqui/XTTS-v2
    
    Note: XTTS-v2 captures emotion from reference audio during voice cloning,
    not through inference parameters. Emotion is embedded in the voice profile.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        use_gpu: bool = False,
    ) -> None:
        self._model_name = model_name
        self._use_gpu = use_gpu
        self._tts = None
        self._torch = None

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
        return self._torch

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
            # Works with both run_app.bat (Windows) and run_app.sh (Mac/Linux)
            import builtins
            import logging
            logger = logging.getLogger(__name__)
            original_input = builtins.input
            
            # Set environment variable to auto-accept license (if TTS supports it)
            os.environ.setdefault("TTS_ACCEPT_LICENSE", "y")
            os.environ.setdefault("COQUI_TTS_ACCEPT_LICENSE", "y")
            
            def auto_accept_input(prompt=""):
                """Auto-accept license agreement by returning 'y' for ALL prompts during TTS init."""
                prompt_lower = prompt.lower()
                prompt_stripped = prompt.strip()
                
                # Always log the prompt for debugging
                if prompt_stripped:
                    logger.debug(f"TTS prompt: {prompt_stripped[:100]}")
                
                # Check if this is a license confirmation prompt
                # Match various license prompt formats
                license_keywords = [
                    "commercial license",
                    "non-commercial cpml",
                    "agree to the terms",
                    "coqui",
                    "cpml",
                    "licensing@coqui.ai",
                    "coqui.ai/cpml",
                    "[y/n]",
                    "y/n",
                    "purchased a commercial license",
                    "otherwise, i agree",
                    "i have purchased",
                    "i agree"
                ]
                
                # Check for license-related keywords
                if any(keyword in prompt_lower for keyword in license_keywords):
                    logger.info("Tự động chấp nhận license agreement cho XTTS-v2 model")
                    message = "✓ Tự động chấp nhận license agreement (non-commercial CPML)"
                    print(message, file=sys.stdout)
                    print(message, file=sys.stderr)
                    return "y"
                
                # Check if prompt is empty, just ">", or starts with "| >" (common in interactive prompts)
                if (not prompt_stripped or 
                    prompt_stripped == ">" or 
                    prompt_stripped.startswith("| >") or
                    prompt_stripped.startswith(">") or
                    prompt_stripped == "|"):
                    # This is a continuation prompt during TTS initialization, auto-accept
                    logger.debug(f"Auto-accepting continuation prompt: '{prompt}'")
                    return "y"
                
                # For ANY prompt during TTS initialization, auto-accept to avoid blocking
                # This ensures smooth model download without user interaction
                # The prompt might be printed separately before input() is called
                logger.info(f"Tự động chấp nhận prompt trong quá trình khởi tạo TTS: '{prompt_stripped[:80]}...'")
                return "y"
            
            # Patch input function BEFORE creating TTS instance
            builtins.input = auto_accept_input
            
            try:
                self._tts = TTS(
                    model_name=self._model_name,
                    progress_bar=False,
                    gpu=self._use_gpu,
                )
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

    def compute_conditioning_latent(self, audio_path: str) -> Tuple[object, object]:
        tts_model = self.tts.synthesizer.tts_model
        config = tts_model.config
        gpt_cond_latent, speaker_embedding = tts_model.get_conditioning_latents(
            audio_path=audio_path,
            gpt_cond_len=getattr(config, 'gpt_cond_len', 6),
            max_ref_length=getattr(config, 'max_ref_len', 30),
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


