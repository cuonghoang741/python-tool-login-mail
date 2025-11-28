from __future__ import annotations

import io
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
            try:
                from TTS.api import TTS  # type: ignore
            except ModuleNotFoundError:
                raise ModuleNotFoundError(
                    "Module 'TTS' chưa được cài đặt.\n"
                    "Vui lòng chạy: pip install TTS"
                )
            # Fix for PyTorch 2.6: patch torch.load to allow loading TTS models
            torch = self.torch
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
            import sys
            logger = logging.getLogger(__name__)
            original_input = builtins.input
            
            def auto_accept_input(prompt=""):
                """Auto-accept license agreement by returning 'y' for license prompts."""
                prompt_lower = prompt.lower()
                # Check if this is a license confirmation prompt
                if any(keyword in prompt_lower for keyword in [
                    "commercial license",
                    "non-commercial cpml",
                    "agree to the terms",
                    "coqui",
                    "[y/n]"
                ]):
                    logger.info("Tự động chấp nhận license agreement cho XTTS-v2 model")
                    # Print to both stdout and stderr to ensure visibility in batch files
                    message = "✓ Tự động chấp nhận license agreement (non-commercial CPML)"
                    print(message, file=sys.stdout)
                    print(message, file=sys.stderr)
                    return "y"
                # For other prompts, use original input (though shouldn't happen in this context)
                return original_input(prompt)
            
            # Patch input function
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


