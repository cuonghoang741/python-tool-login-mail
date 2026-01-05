from __future__ import annotations

import inspect
import logging
import re
import tempfile
import threading
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from tool_voices.domain import VoiceProfile
from tool_voices.repositories.voice_repository import VoiceRepository
from tool_voices.services.voice_clone import VoiceCloneService
from tool_voices.services.xtts_gateway import XTTSModelGateway


class VoiceSynthesisService:
    """
    Generate speech from text using XTTS-v2 voice models.
    
    Note: XTTS-v2 captures emotion from reference audio during voice cloning,
    not through inference parameters. The emotion/intensity settings here
    adjust voice characteristics (temperature, top_p, speed) to complement
    the emotion already captured in the voice profile.
    """
    
    _EMOTION_ALIAS: Dict[str, str] = {
        "neutral": "Neutral",
        "happy": "Happy",
        "angry": "Angry",
        "sad": "Sad",
        "surprised": "Surprised",
        "afraid": "Afraid",
    }

    def __init__(
        self,
        voice_clone_service: VoiceCloneService,
        gateway: Optional[XTTSModelGateway] = None,
        repository: Optional[VoiceRepository] = None,
        output_dir: Optional[Path] = None,
        enable_latent_cache: bool = True,
        max_cache_size: int = 10,
    ) -> None:
        self._voice_clone_service = voice_clone_service
        self._gateway = gateway or XTTSModelGateway()
        self._repository = repository or VoiceRepository(Path("./voices"))
        self._output_dir: Path = (output_dir or Path("./outputs")).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(__name__)
        self._log_callback: Optional[Callable[[str], None]] = None
        
        # Conditioning latents cache for faster repeated voice usage
        # Key: voice_name, Value: (gpt_latent, speaker_embedding, embedding_path_mtime)
        self._enable_latent_cache = enable_latent_cache
        self._max_cache_size = max_cache_size
        self._latent_cache: Dict[str, Tuple[object, object, Optional[float]]] = {}
    
    def set_log_callback(self, callback: Optional[Callable[[str], None]]) -> None:
        """Set callback function to receive log messages for UI display."""
        self._log_callback = callback
    
    def _log(self, message: str, level: str = "info") -> None:
        """Log message both to logger and UI callback."""
        if level == "info":
            self._logger.info(message)
        elif level == "warning":
            self._logger.warning(message)
        elif level == "error":
            self._logger.error(message)
        else:
            self._logger.debug(message)
        
        # Send to UI callback if available
        if self._log_callback:
            try:
                self._log_callback(message)
            except Exception:
                pass  # Ignore callback errors to avoid breaking synthesis

    def synthesize(
        self,
        text: str,
        voice_name: str,
        emotion: str,
        intensity: float,
        output_path: Optional[Path] = None,
        max_workers: int = 1,
        advanced_params: Optional[Dict[str, object]] = None,
        language_override: Optional[str] = None,
        use_streaming: bool = True,
    ) -> Path:
        if not text.strip():
            raise ValueError("Văn bản đầu vào không được để trống.")

        # Check if using default voice
        if voice_name.startswith("default:"):
            return self._synthesize_with_default_voice(
                text,
                voice_name,
                emotion,
                intensity,
                output_path,
                advanced_params,
                language_override=language_override,
            )

        voice = self._load_voice(voice_name)
        # Nếu người dùng chọn language cụ thể trong UI thì ưu tiên, ngược lại tự select
        language = language_override or self._select_language(voice, text)
        destination = output_path or self._build_output_path(voice_name, emotion)

        self._log("🔧 Đang tải conditioning latents...")
        gpt_latent, speaker_embedding = self._load_conditionings(voice)
        self._log("✅ Đã tải conditioning latents")
        
        self._log("⚙️ Đang chuẩn bị inference parameters...")
        inference_kwargs = self._prepare_inference_kwargs(
            emotion, intensity, advanced_params or {}
        )
        self._log("✅ Đã chuẩn bị inference parameters")
        
        # Check if text needs to be split into chunks
        text_chunks = self._split_text_into_chunks(text, language)
        
        self._log(
            f"📊 Phân tích: {len(text)} ký tự → {len(text_chunks)} chunk(s), "
            f"Ngôn ngữ: {language}"
        )
        
        self._logger.info(
            "Synthesizing %s chars (%d chunks) with voice '%s' (emotion=%s, intensity=%.2f, language=%s)",
            len(text),
            len(text_chunks),
            voice_name,
            emotion,
            intensity,
            language,
        )
        self._logger.debug(
            "Note: XTTS-v2 emotion is captured from reference audio. "
            "Intensity adjusts temperature/top_p/speed parameters."
        )
        
        # If only one chunk, process normally
        if len(text_chunks) == 1:
            self._log("🔄 Xử lý 1 chunk duy nhất...")
            overall_start = time.time()
            audio = self._run_inference(
                use_streaming=use_streaming,
                text=text_chunks[0],
                language=language,
                gpt_cond_latent=gpt_latent,
                speaker_embedding=speaker_embedding,
                **inference_kwargs,
            )
            total_elapsed = time.time() - overall_start
            self._log(f"✅ Hoàn tất xử lý chunk (tổng {total_elapsed:.2f}s)")
        else:
            # Process multiple chunks in parallel and concatenate
            sample_rate = self._resolve_sample_rate()
            
            # Use parallel processing if max_workers > 1
            # Note: With lock, parallel processing may not be much faster, but still useful for I/O bound operations
            if max_workers > 1 and len(text_chunks) > 1:
                self._log(f"⚡ Xử lý song song: {len(text_chunks)} chunks với {max_workers} workers")
                try:
                    audio_chunks = self._process_chunks_parallel(
                        text_chunks,
                        language,
                        gpt_latent,
                        speaker_embedding,
                        inference_kwargs,
                        max_workers,
                    )
                    self._log("⏱️ Đã hoàn tất xử lý song song.")
                except Exception as e:
                    self._log(f"⚠️ Xử lý song song thất bại, chuyển sang tuần tự: {str(e)}", "warning")
                    self._logger.error("Parallel processing failed, falling back to sequential: %s", e)
                    # Fallback to sequential processing on error
                    audio_chunks = []
                    start_time = time.time()
                    for i, chunk in enumerate(text_chunks):
                        self._log(f"📝 Chunk {i + 1}/{len(text_chunks)}: {len(chunk)} ký tự")
                        self._logger.info("Processing chunk %d/%d (%d chars)", i + 1, len(text_chunks), len(chunk))
                        chunk_audio = self._run_inference(
                            use_streaming=use_streaming,
                            text=chunk,
                            language=language,
                            gpt_cond_latent=gpt_latent,
                            speaker_embedding=speaker_embedding,
                            **inference_kwargs,
                        )
                        audio_chunks.append(chunk_audio)
                        elapsed = time.time() - start_time
                        remaining = len(text_chunks) - (i + 1)
                        avg = elapsed / (i + 1)
                        eta = avg * remaining if remaining > 0 else 0
                        self._log(
                            f"✅ Hoàn tất chunk {i + 1}/{len(text_chunks)} "
                            f"({elapsed:.2f}s, ước còn ~{eta:.2f}s)"
                        )
            else:
                # Sequential processing
                self._log(f"📝 Xử lý tuần tự: {len(text_chunks)} chunks")
                audio_chunks = []
                start_time = time.time()
                for i, chunk in enumerate(text_chunks):
                    self._log(f"📝 Chunk {i + 1}/{len(text_chunks)}: {len(chunk)} ký tự")
                    self._logger.info("Processing chunk %d/%d (%d chars)", i + 1, len(text_chunks), len(chunk))
                    chunk_audio = self._run_inference(
                        use_streaming=use_streaming,
                        text=chunk,
                        language=language,
                        gpt_cond_latent=gpt_latent,
                        speaker_embedding=speaker_embedding,
                        **inference_kwargs,
                    )
                    audio_chunks.append(chunk_audio)
                    elapsed = time.time() - start_time
                    remaining = len(text_chunks) - (i + 1)
                    avg = elapsed / (i + 1)
                    eta = avg * remaining if remaining > 0 else 0
                    self._log(
                        f"✅ Hoàn tất chunk {i + 1}/{len(text_chunks)} "
                        f"({elapsed:.2f}s, ước còn ~{eta:.2f}s)"
                    )
                total_elapsed = time.time() - start_time
                self._log(f"⏱️ Tổng thời gian synth: {total_elapsed:.2f}s (tuần tự)")
            
            # Concatenate all audio chunks in order
            self._log(f"🔗 Đang ghép {len(audio_chunks)} chunks thành audio cuối cùng...")
            audio = np.concatenate(audio_chunks)
            self._logger.info("Concatenated %d audio chunks into final audio", len(audio_chunks))
            self._log(f"✅ Đã ghép xong {len(audio_chunks)} chunks")
        
        sample_rate = self._resolve_sample_rate()
        self._log(f"💾 Đang ghi file audio: {destination.name}")
        self._write_wav(audio, sample_rate, destination)
        self._logger.info("Audio written to %s", destination)
        self._log(f"✅ Đã ghi file thành công: {destination.name}")
        return destination

    def _load_voice(self, voice_name: str) -> VoiceProfile:
        self._log(f"📂 Đang tải giọng: {voice_name}")
        voice = self._repository.load_voice(voice_name)
        if voice is None:
            error_msg = f"Giọng '{voice_name}' không tồn tại."
            self._log(error_msg, "error")
            raise ValueError(error_msg)
        self._log(f"✅ Đã tải giọng: {voice_name}")
        return voice

    def _load_conditionings(self, voice: VoiceProfile) -> Tuple[object, object]:
        """Load conditioning latents with caching support."""
        torch = self._gateway.torch
        voice_name = voice.name
        
        # Check embedding_path properly (avoid array comparison issues)
        has_embedding = voice.embedding_path is not None
        embedding_mtime: Optional[float] = None
        
        if has_embedding:
            try:
                embedding_exists = voice.embedding_path.exists()
                if embedding_exists:
                    embedding_mtime = voice.embedding_path.stat().st_mtime
            except (AttributeError, TypeError):
                # If embedding_path is not a Path-like object, treat as missing
                embedding_exists = False
        else:
            embedding_exists = False
        
        # Check cache first
        if self._enable_latent_cache and voice_name in self._latent_cache:
            cached_gpt, cached_speaker, cached_mtime = self._latent_cache[voice_name]
            
            # Validate cache: check if embedding file was modified
            cache_valid = True
            if has_embedding and embedding_exists:
                if cached_mtime != embedding_mtime:
                    cache_valid = False
                    self._logger.debug(f"Cache invalidated for '{voice_name}': embedding file changed")
            
            if cache_valid:
                self._log(f"⚡ Sử dụng cached latents cho '{voice_name}' (tiết kiệm ~300ms)")
                device = getattr(self._gateway.tts.synthesizer.tts_model, "device", "cpu")
                return cached_gpt.to(device), cached_speaker.to(device)
            else:
                # Remove invalid cache entry
                del self._latent_cache[voice_name]
        
        # Load conditionings from file or compute from samples
        if has_embedding and embedding_exists:
            # Fix for PyTorch 2.6: set weights_only=False
            data = torch.load(voice.embedding_path, map_location="cpu", weights_only=False)
            gpt_latent = data["gpt_latent"]
            speaker_embedding = data["speaker_embedding"]
        else:
            # Check samples list properly
            if not voice.samples or len(voice.samples) == 0:
                raise ValueError("Không tìm thấy mẫu âm thanh cho giọng này.")
            gpt_latent, speaker_embedding = self._gateway.compute_conditioning_latent(
                str(voice.samples[0])
            )

        device = getattr(self._gateway.tts.synthesizer.tts_model, "device", "cpu")
        gpt_latent = gpt_latent.to(device)
        speaker_embedding = speaker_embedding.to(device)
        
        # Cache the latents (on CPU to save GPU memory)
        if self._enable_latent_cache:
            # Evict oldest entries if cache is full
            if len(self._latent_cache) >= self._max_cache_size:
                oldest_key = next(iter(self._latent_cache))
                del self._latent_cache[oldest_key]
                self._logger.debug(f"Evicted oldest cache entry: '{oldest_key}'")
            
            # Store on CPU to save GPU memory
            self._latent_cache[voice_name] = (
                gpt_latent.cpu().clone(),
                speaker_embedding.cpu().clone(),
                embedding_mtime,
            )
            self._log(f"💾 Đã cache latents cho '{voice_name}'")
        
        return gpt_latent, speaker_embedding
    
    def clear_latent_cache(self) -> None:
        """Clear the conditioning latents cache."""
        self._latent_cache.clear()
        self._logger.info("Conditioning latents cache cleared")

    def _prepare_inference_kwargs(
        self, 
        emotion: str, 
        intensity: float,
        advanced_params: Dict[str, object],
    ) -> Dict[str, object]:
        """
        Prepare inference parameters for XTTS-v2.
        
        IMPORTANT: XTTS-v2 does NOT support emotion/emotion_strength parameters directly.
        Emotion is primarily captured from reference audio during voice cloning.
        
        However, we can adjust voice characteristics (temperature, top_p, speed, etc.)
        to complement the emotion and make it more pronounced:
        - Temperature: Lower = more deterministic/stable, Higher = more varied
        - Top-p: Lower = more focused, Higher = more diverse
        - Speed: Faster for excited emotions, slower for subdued emotions
        - Repetition penalty: Higher = less repetition (good for emotional speech)
        
        Args:
            emotion: Emotion name - affects speed and parameter adjustments
            intensity: Intensity value 0.0-1.0 - affects temperature, top_p, and speed range
            advanced_params: Dictionary of advanced parameters (temperature, top_p, etc.)
                            If provided, these override auto-calculated values
        
        Returns:
            Dictionary of inference parameters
        """
        intensity_clamped = float(max(0.0, min(1.0, intensity)))
        emotion_lower = emotion.lower()
        inference_signature = inspect.signature(self._gateway.tts.synthesizer.tts_model.inference)
        param_names = [p.name for p in inference_signature.parameters.values()]

        kwargs: Dict[str, object] = {}
        
        # Determine emotion characteristics
        is_excited = emotion_lower in ["angry", "happy", "surprised"]
        is_subdued = emotion_lower in ["sad", "afraid"]
        is_neutral = emotion_lower == "neutral"
        
        # Temperature: use manual value if provided, otherwise auto-adjust based on emotion + intensity
        if "temperature" in param_names:
            if "temperature" in advanced_params:
                kwargs["temperature"] = float(advanced_params["temperature"])
            else:
                # Base temperature varies by emotion type
                if is_excited:
                    # Excited emotions: lower temperature (more deterministic) at high intensity
                    base_temp = 0.75
                    range_temp = 0.25  # 0.5 to 0.75
                elif is_subdued:
                    # Subdued emotions: slightly higher temperature (more varied)
                    base_temp = 0.85
                    range_temp = 0.2  # 0.65 to 0.85
                else:
                    # Neutral: middle range
                    base_temp = 0.8
                    range_temp = 0.2  # 0.6 to 0.8
                
                # Higher intensity = lower temperature (more focused/stronger)
                kwargs["temperature"] = base_temp - (intensity_clamped * range_temp)
        
        # Top-p: use manual value if provided, otherwise auto-adjust
        if "top_p" in param_names:
            if "top_p" in advanced_params:
                kwargs["top_p"] = float(advanced_params["top_p"])
            else:
                # Higher intensity = lower top_p (more focused)
                if is_excited:
                    # Excited: more focused at high intensity
                    base_top_p = 0.9
                    range_top_p = 0.25  # 0.65 to 0.9
                elif is_subdued:
                    # Subdued: slightly more diverse
                    base_top_p = 0.95
                    range_top_p = 0.15  # 0.8 to 0.95
                else:
                    # Neutral: middle range
                    base_top_p = 0.9
                    range_top_p = 0.2  # 0.7 to 0.9
                
                kwargs["top_p"] = base_top_p - (intensity_clamped * range_top_p)
        
        # Top-k: use manual value if provided, otherwise adjust based on emotion
        if "top_k" in param_names:
            if "top_k" in advanced_params:
                kwargs["top_k"] = int(advanced_params["top_k"])
            else:
                # Lower top_k for more focused output (stronger emotion)
                if is_excited:
                    kwargs["top_k"] = max(20, int(50 - (intensity_clamped * 30)))  # 20-50
                elif is_subdued:
                    kwargs["top_k"] = max(30, int(60 - (intensity_clamped * 20)))  # 30-60
                else:
                    kwargs["top_k"] = max(40, int(50 - (intensity_clamped * 10)))  # 40-50
        
        # Repetition penalty: use manual value if provided, otherwise adjust
        if "repetition_penalty" in param_names:
            if "repetition_penalty" in advanced_params:
                kwargs["repetition_penalty"] = float(advanced_params["repetition_penalty"])
            else:
                # Higher penalty for emotional speech (less repetition)
                if is_excited or is_subdued:
                    # Emotional speech: higher penalty to avoid repetition
                    kwargs["repetition_penalty"] = 10.0 + (intensity_clamped * 5.0)  # 10.0-15.0
                else:
                    kwargs["repetition_penalty"] = 10.0
        
        # Length penalty: use manual value if provided
        if "length_penalty" in param_names and "length_penalty" in advanced_params:
            kwargs["length_penalty"] = float(advanced_params["length_penalty"])
        
        # Speed: use manual value if provided, otherwise auto-adjust based on emotion
        if "speed" in param_names:
            if "speed" in advanced_params:
                kwargs["speed"] = float(advanced_params["speed"])
            else:
                # Speed adjustment based on emotion type and intensity
                if is_excited:
                    # Excited emotions: faster speech, more pronounced at high intensity
                    kwargs["speed"] = 1.0 + (intensity_clamped * 0.2)  # 1.0 to 1.2
                elif is_subdued:
                    # Subdued emotions: slower speech, more pronounced at high intensity
                    kwargs["speed"] = 1.0 - (intensity_clamped * 0.15)  # 0.85 to 1.0
                else:
                    # Neutral: slight variation
                    kwargs["speed"] = 1.0 + (intensity_clamped * 0.05) - 0.025  # 0.975 to 1.025
        
        # Num beams: use manual value if provided
        if "num_beams" in param_names and "num_beams" in advanced_params:
            kwargs["num_beams"] = int(advanced_params["num_beams"])
        
        # Do sample: use manual value if provided
        if "do_sample" in param_names and "do_sample" in advanced_params:
            kwargs["do_sample"] = bool(advanced_params["do_sample"])

        return kwargs

    def _run_inference(self, use_streaming: bool = True, **kwargs: object) -> np.ndarray:
        """
        Run inference with optional streaming for real-time progress.
        
        Args:
            use_streaming: If True, use inference_stream for chunk-by-chunk progress
            **kwargs: Inference parameters
        
        Returns:
            Audio data as numpy array
        """
        tts_model = self._gateway.tts.synthesizer.tts_model
        
        # Check if streaming is available and enabled
        has_streaming = hasattr(tts_model, 'inference_stream')
        
        if use_streaming and has_streaming:
            return self._run_inference_stream(tts_model, **kwargs)
        else:
            return self._run_inference_batch(tts_model, **kwargs)
    
    def _run_inference_batch(self, tts_model, **kwargs: object) -> np.ndarray:
        """Run standard batch inference."""
        self._log("🤖 Đang chạy inference (có thể mất vài giây)...")
        result = tts_model.inference(**kwargs)
        self._log("✅ Inference hoàn tất")
        return self._extract_audio_from_result(result)
    
    def _run_inference_stream(self, tts_model, **kwargs: object) -> np.ndarray:
        """
        Run streaming inference with real-time progress from model.
        
        Uses inference_stream() which yields audio chunks as they are generated,
        providing natural progress tracking based on model output.
        """
        self._log("🎵 Đang chạy streaming inference...")
        
        # Streaming parameters
        stream_chunk_size = kwargs.pop('stream_chunk_size', 20)  # GPT tokens per chunk
        overlap_wav_len = kwargs.pop('overlap_wav_len', 1024)  # Overlap samples
        
        audio_chunks = []
        chunk_count = 0
        total_samples = 0
        sample_rate = self._resolve_sample_rate()
        start_time = time.time()
        
        try:
            # inference_stream yields audio chunks as generator
            stream_generator = tts_model.inference_stream(
                stream_chunk_size=stream_chunk_size,
                overlap_wav_len=overlap_wav_len,
                **kwargs
            )
            
            for chunk in stream_generator:
                chunk_count += 1
                
                # Extract audio from chunk (handle tensor/dict)
                chunk_audio = self._extract_audio_from_result(chunk)
                audio_chunks.append(chunk_audio)
                
                # Calculate real progress based on generated audio
                chunk_samples = len(chunk_audio)
                total_samples += chunk_samples
                duration_generated = total_samples / sample_rate
                elapsed = time.time() - start_time
                
                # Real-time speed ratio (generated audio vs real time)
                speed_ratio = duration_generated / elapsed if elapsed > 0 else 0
                
                self._log(
                    f"🔊 Chunk {chunk_count}: +{duration_generated:.1f}s audio | "
                    f"Tốc độ: {speed_ratio:.1f}x realtime"
                )
            
            # Concatenate all chunks
            if audio_chunks:
                full_audio = np.concatenate(audio_chunks)
                total_duration = len(full_audio) / sample_rate
                total_elapsed = time.time() - start_time
                
                self._log(
                    f"✅ Streaming hoàn tất: {chunk_count} chunks, "
                    f"{total_duration:.1f}s audio trong {total_elapsed:.1f}s "
                    f"({total_duration/total_elapsed:.1f}x realtime)"
                )
                return full_audio
            else:
                raise RuntimeError("Streaming inference returned no audio chunks")
                
        except Exception as e:
            self._logger.warning(f"Streaming failed, falling back to batch: {e}")
            self._log(f"⚠️ Streaming thất bại, chuyển sang batch mode...")
            # Fallback to batch inference
            return self._run_inference_batch(tts_model, **kwargs)
    
    def _extract_audio_from_result(self, result) -> np.ndarray:
        """Extract numpy audio array from inference result."""
        if isinstance(result, dict):
            audio = result.get("wav")
            if audio is None:
                audio = result.get("audio")
        else:
            audio = result
        
        if audio is None:
            raise RuntimeError("XTTS inference returned no audio data.")

        if hasattr(audio, "detach"):
            audio = audio.detach()
        if hasattr(audio, "cpu"):
            audio = audio.cpu()
        audio_np = audio.numpy() if hasattr(audio, "numpy") else np.asarray(audio)
        if audio_np.ndim > 1:
            audio_np = audio_np[0]
        return audio_np

    def _resolve_sample_rate(self) -> int:
        tts_model = self._gateway.tts.synthesizer.tts_model
        if hasattr(tts_model, "output_sample_rate"):
            return int(tts_model.output_sample_rate)
        config = getattr(tts_model, "config", None)
        if config and hasattr(config, "audio"):
            audio_cfg = config.audio
            if isinstance(audio_cfg, dict):
                return int(audio_cfg.get("sample_rate", 24000))
        return 24000

    def _write_wav(self, data: np.ndarray, sample_rate: int, destination: Path) -> None:
        """Write audio data to WAV file with optimized I/O."""
        destination.parent.mkdir(parents=True, exist_ok=True)
        clipped = np.clip(data, -1.0, 1.0)
        
        # Try soundfile first (faster ~20%)
        try:
            import soundfile as sf
            # soundfile works with float data directly, no need to convert to int16
            sf.write(str(destination), clipped, sample_rate, format='WAV', subtype='PCM_16')
            return
        except ImportError:
            pass  # Fall back to wave module
        except Exception as e:
            self._logger.debug(f"soundfile failed, using wave: {e}")
        
        # Fallback to standard wave module
        pcm = (clipped * 32767).astype(np.int16)
        with wave.open(str(destination), "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(pcm.tobytes())

    def _build_output_path(self, voice_name: str, emotion: str) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        voice_slug = self._slugify(voice_name)
        emotion_slug = self._slugify(emotion)
        return self._output_dir / f"{voice_slug}_{emotion_slug}_{timestamp}.wav"

    def _synthesize_with_default_voice(
        self,
        text: str,
        voice_name: str,
        emotion: str,
        intensity: float,
        output_path: Optional[Path] = None,
        advanced_params: Optional[Dict[str, object]] = None,
        language_override: Optional[str] = None,
    ) -> Path:
        """Synthesize using default XTTS voice by creating default conditioning latents."""
        # Extract language code (e.g., "default:en" -> "en")
        language = (language_override or voice_name.replace("default:", "")).strip()
        
        # Validate language
        supported_languages = self._get_supported_languages()
        if language not in supported_languages:
            # Fallback to English if language not supported
            self._logger.warning(f"Language '{language}' not supported, using 'en'")
            language = "en"
        
        # Auto-detect language from text if needed
        if language == "en":
            if self._looks_vietnamese(text):
                language = "vi" if "vi" in self._get_supported_languages() else "en"
            elif self._looks_spanish(text):
                language = "es" if "es" in self._get_supported_languages() else "en"
        
        destination = output_path or self._build_output_path(f"default_{language}", emotion)
        
        self._log(f"🎤 Sử dụng default voice (neutral) cho ngôn ngữ: {language}")
        self._log(f"🌐 Ngôn ngữ: {language}")
        
        try:
            # Create default conditioning latents using model's default speaker
            # We'll use a neutral/default speaker embedding
            self._log("🔧 Đang tạo default conditioning latents...")
            gpt_latent, speaker_embedding = self._create_default_conditionings()
            self._log("✅ Đã tạo default conditioning latents")
            
            # Prepare inference parameters
            self._log("⚙️ Đang chuẩn bị inference parameters...")
            inference_kwargs = self._prepare_inference_kwargs(
                emotion, intensity, advanced_params or {}
            )
            self._log("✅ Đã chuẩn bị inference parameters")
            
            # Split text into chunks if needed
            text_chunks = self._split_text_into_chunks(text, language)
            
            self._log(
                f"📊 Phân tích: {len(text)} ký tự → {len(text_chunks)} chunk(s), "
                f"Ngôn ngữ: {language}"
            )
            
            # Process chunks
            if len(text_chunks) == 1:
                self._log("🔄 Xử lý 1 chunk duy nhất...")
                audio = self._run_inference(
                    use_streaming=False,  # Default voice uses batch mode
                    text=text_chunks[0],
                    language=language,
                    gpt_cond_latent=gpt_latent,
                    speaker_embedding=speaker_embedding,
                    **inference_kwargs,
                )
                self._log("✅ Hoàn tất xử lý chunk")
            else:
                # Process multiple chunks sequentially
                self._log(f"📝 Xử lý tuần tự: {len(text_chunks)} chunks")
                sample_rate = self._resolve_sample_rate()
                audio_chunks = []
                for i, chunk in enumerate(text_chunks):
                    self._log(f"📝 Chunk {i + 1}/{len(text_chunks)}: {len(chunk)} ký tự")
                    chunk_audio = self._run_inference(
                        use_streaming=False,  # Default voice uses batch mode
                        text=chunk,
                        language=language,
                        gpt_cond_latent=gpt_latent,
                        speaker_embedding=speaker_embedding,
                        **inference_kwargs,
                    )
                    audio_chunks.append(chunk_audio)
                    self._log(f"✅ Hoàn tất chunk {i + 1}/{len(text_chunks)}")
                
                # Concatenate audio chunks
                self._log("🔗 Đang nối các chunks...")
                audio = np.concatenate(audio_chunks)
            
            # Write to file
            sample_rate = self._resolve_sample_rate()
            self._write_wav(audio, sample_rate, destination)
            self._log(f"✅ Đã ghi file thành công: {destination.name}")
            return destination
            
        except Exception as e:
            error_msg = f"Lỗi khi sử dụng default voice: {str(e)}"
            self._log(error_msg, "error")
            self._logger.error(error_msg, exc_info=True)
            raise RuntimeError(error_msg) from e
    
    def _create_default_conditionings(self) -> Tuple[object, object]:
        """Create default conditioning latents for default voice using a generated audio sample."""
        try:
            # Create a simple audio sample (sine wave) to use as reference
            # This ensures we get proper conditioning latents with correct shapes
            import numpy as np
            import tempfile
            import os
            import wave
            
            sample_rate = 24000
            duration = 1.0  # 1 second of audio
            frequency = 440.0  # A4 note (neutral tone)
            
            # Generate a simple sine wave
            t = np.linspace(0, duration, int(sample_rate * duration), False)
            audio = np.sin(2 * np.pi * frequency * t).astype(np.float32)
            
            # Normalize and convert to int16
            audio = np.clip(audio, -1.0, 1.0)
            audio_int16 = (audio * 32767).astype(np.int16)
            
            # Save to temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
                tmp_path = tmp_file.name
                # Write WAV file
                with wave.open(tmp_path, "wb") as wav_file:
                    wav_file.setnchannels(1)
                    wav_file.setsampwidth(2)
                    wav_file.setframerate(sample_rate)
                    wav_file.writeframes(audio_int16.tobytes())
            
            # Use this audio to create conditioning latents (same as trained voices)
            # This ensures correct shapes and proper conditioning
            gpt_latent, speaker_embedding = self._gateway.compute_conditioning_latent(tmp_path)
            
            # Clean up temp file
            try:
                os.unlink(tmp_path)
            except Exception:
                pass
            
            return gpt_latent, speaker_embedding
            
        except Exception as e:
            # Fallback: try to get shape from an existing voice or use model defaults
            self._logger.warning(f"Could not create default conditionings from audio: {e}")
            try:
                # Try to load a voice to get correct shapes
                voices = self._repository.list_voices()
                if voices:
                    # Use first available voice to get correct shape
                    voice = self._repository.load_voice(voices[0])
                    if voice and voice.samples:
                        gpt_latent, speaker_embedding = self._gateway.compute_conditioning_latent(
                            str(voice.samples[0])
                        )
                        # Use zeros to create a neutral version (average out)
                        torch = self._gateway.torch
                        device = speaker_embedding.device
                        # Create neutral latents by using very small values
                        gpt_latent = torch.zeros_like(gpt_latent)
                        speaker_embedding = torch.zeros_like(speaker_embedding)
                        return gpt_latent, speaker_embedding
            except Exception as e2:
                self._logger.error(f"Fallback also failed: {e2}")
            
            # Last resort: raise error with helpful message
            raise RuntimeError(
                "Could not create default voice conditionings. "
                "Please train at least one voice first, or ensure TTS model is properly loaded."
            ) from e

    def _select_language(self, voice: VoiceProfile, text: str) -> str:
        # Get supported languages from model
        supported_languages = self._get_supported_languages()
        
        # If voice has explicit language setting
        if voice.language and voice.language != "auto":
            language = voice.language
            # Check if language is supported, if not fallback to default
            if language in supported_languages:
                return language
            else:
                self._logger.warning(
                    f"Language '{language}' is not supported. Supported: {supported_languages}. "
                    f"Falling back to 'en'."
                )
                return "en"
        
        # Auto-detect language from text
        if self._looks_vietnamese(text):
            # XTTS v2 doesn't support 'vi', use 'en' as fallback
            # Vietnamese text can still be processed with English model
            if "vi" in supported_languages:
                return "vi"
            else:
                self._logger.info(
                    "Vietnamese text detected but 'vi' not supported. Using 'en' instead."
                )
                return "en"
        if self._looks_spanish(text):
            if "es" in supported_languages:
                return "es"
            else:
                return "en"
        return "en"
    
    def _get_supported_languages(self) -> list:
        """Get list of supported languages from the TTS model."""
        try:
            tts_model = self._gateway.tts.synthesizer.tts_model
            if hasattr(tts_model, 'config') and hasattr(tts_model.config, 'languages'):
                languages = tts_model.config.languages
                # Convert to list if it's a numpy array or other iterable
                if hasattr(languages, 'tolist'):
                    return languages.tolist()
                elif isinstance(languages, (list, tuple)):
                    return list(languages)
                else:
                    return list(languages) if languages else []
        except Exception:
            pass
        # Default fallback - common XTTS languages
        return ["en", "es", "fr", "de", "it", "pt", "pl", "tr", "ru", "nl", "cs", "ar", "zh-cn", "hu", "ko", "ja", "hi"]

    def _normalize_emotion(self, emotion: str) -> str:
        key = emotion.lower()
        return self._EMOTION_ALIAS.get(key, emotion.capitalize())

    def _slugify(self, value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", "-", value)
        return value.strip("-") or "voice"

    def _looks_vietnamese(self, text: str) -> bool:
        vietnamese_chars = set("ăâêôơưđáàảãạắằẳẵặấầẩẫậéèẻẽẹếềểễệíìỉĩịóòỏõọốồổỗộớờởỡợúùủũụứừửữựýỳỷỹỵ")
        text_lower = text.lower()
        return any(char in vietnamese_chars for char in text_lower)

    def _looks_spanish(self, text: str) -> bool:
        spanish_chars = set("áéíñóúü¿¡")
        text_lower = text.lower()
        return any(char in spanish_chars for char in text_lower)

    def _estimate_token_count(self, text: str, language: str) -> int:
        """
        Fast token count estimation without calling tokenizer.
        
        Uses language-aware character-to-token ratios:
        - English/Latin: ~1 token per 3-4 characters
        - CJK (Chinese, Japanese, Korean): ~1 token per 1.5-2 characters
        - Vietnamese: ~1 token per 2-2.5 characters (diacritics count)
        
        This is much faster than tokenizer.encode() for word-level estimation.
        """
        text_len = len(text)
        if text_len == 0:
            return 0
        
        # Language-specific ratios (chars per token)
        ratios = {
            "en": 3.5,
            "es": 3.0,
            "fr": 3.0,
            "de": 3.0,
            "it": 3.0,
            "pt": 3.0,
            "pl": 2.8,
            "tr": 3.0,
            "ru": 2.5,
            "nl": 3.2,
            "cs": 2.8,
            "ar": 2.0,
            "zh-cn": 1.5,
            "hu": 2.8,
            "ko": 1.8,
            "ja": 1.5,
            "hi": 2.0,
            "vi": 2.2,
        }
        
        ratio = ratios.get(language, 3.0)  # Default to English-like ratio
        
        # Add small buffer for safety (underestimate tokens = safer chunking)
        estimated = int(text_len / ratio) + 1
        return max(1, estimated)  # At least 1 token


    def _split_text_into_chunks(self, text: str, language: str) -> List[str]:
        """Split text into chunks that fit within XTTS token limit (400 tokens)."""
        try:
            tts_model = self._gateway.tts.synthesizer.tts_model
            if not hasattr(tts_model, 'tokenizer') or tts_model.tokenizer is None:
                # Fallback: use character-based splitting
                return self._split_text_by_chars(text, max_chars=750)
            
            tokenizer = tts_model.tokenizer
            max_tokens = getattr(tts_model.args, 'gpt_max_text_tokens', 400)
            # Use a conservative safety margin (80% of max = 320 tokens to be very safe)
            safe_max_tokens = int(max_tokens * 0.8)
            
            # Get char limit for the language
            char_limit = tokenizer.char_limits.get(language, 250) if hasattr(tokenizer, 'char_limits') else 250
            # Use a conservative char limit (70% of limit) to ensure both char and token limits are respected
            safe_char_limit = int(char_limit * 0.7)
            
            # Try to use split_sentence if available
            try:
                from TTS.tts.layers.xtts.tokenizer import split_sentence
                sentences = split_sentence(text, language, safe_char_limit)
            except Exception:
                # Fallback to simple sentence splitting
                sentences = self._split_into_sentences(text)
            
            chunks = []
            current_chunk = ""
            current_tokens = 0
            current_chars = 0
            
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                
                # Check both char limit and token limit
                sentence_chars = len(sentence)
                
                # Estimate tokens for this sentence
                # Use fast estimation for sentences (only tokenize full sentences, not individual words)
                try:
                    tokens = tokenizer.encode(sentence, lang=language)
                    # tokenizer.encode returns a list of token IDs
                    if isinstance(tokens, (list, tuple)):
                        token_count = len(tokens)
                    elif hasattr(tokens, '__len__'):
                        token_count = len(tokens)
                    else:
                        token_count = self._estimate_token_count(sentence, language)
                except Exception:
                    # Fallback: use fast estimation
                    token_count = self._estimate_token_count(sentence, language)
                
                # If single sentence exceeds limits, split it further
                if token_count > safe_max_tokens or sentence_chars > safe_char_limit:
                    # Split long sentence by words using FAST estimation (no tokenizer calls per word)
                    words = sentence.split()
                    word_chunk = ""
                    word_tokens = 0
                    word_chars = 0
                    
                    for word in words:
                        word_len = len(word)
                        # Use fast estimation instead of tokenizer.encode per word
                        # This saves significant time for long sentences
                        word_token_count = self._estimate_token_count(word, language)
                        
                        would_exceed_tokens = word_tokens + word_token_count > safe_max_tokens
                        would_exceed_chars = word_chars + word_len + 1 > safe_char_limit  # +1 for space
                        
                        if (would_exceed_tokens or would_exceed_chars) and word_chunk:
                            chunks.append(word_chunk.strip())
                            word_chunk = word
                            word_tokens = word_token_count
                            word_chars = word_len
                        else:
                            word_chunk += " " + word if word_chunk else word
                            word_tokens += word_token_count
                            word_chars += word_len + (1 if word_chunk else 0)
                    
                    if word_chunk:
                        would_exceed_tokens = current_tokens + word_tokens > safe_max_tokens
                        would_exceed_chars = current_chars + word_chars + 1 > safe_char_limit
                        
                        if (would_exceed_tokens or would_exceed_chars) and current_chunk:
                            chunks.append(current_chunk.strip())
                            current_chunk = word_chunk
                            current_tokens = word_tokens
                            current_chars = word_chars
                        else:
                            current_chunk += " " + word_chunk if current_chunk else word_chunk
                            current_tokens += word_tokens
                            current_chars += word_chars + (1 if current_chunk else 0)
                else:
                    # Check if adding this sentence would exceed limits (both token and char)
                    would_exceed_tokens = current_tokens + token_count > safe_max_tokens
                    would_exceed_chars = current_chars + sentence_chars + 1 > safe_char_limit  # +1 for space
                    
                    if (would_exceed_tokens or would_exceed_chars) and current_chunk:
                        chunks.append(current_chunk.strip())
                        current_chunk = sentence
                        current_tokens = token_count
                        current_chars = sentence_chars
                    else:
                        current_chunk += " " + sentence if current_chunk else sentence
                        current_tokens += token_count
                        current_chars += sentence_chars + (1 if current_chunk else 0)
            
            # Add remaining chunk
            if current_chunk.strip():
                chunks.append(current_chunk.strip())
            
            return chunks if chunks else [text]
            
        except Exception as e:
            self._logger.warning("Error splitting text by tokens, using character-based fallback: %s", e)
            return self._split_text_by_chars(text, max_chars=500)

    def _split_text_by_chars(self, text: str, max_chars: int = 500) -> List[str]:
        """Fallback: split text by character count."""
        if len(text) <= max_chars:
            return [text]
        
        chunks = []
        sentences = self._split_into_sentences(text)
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            if len(current_chunk) + len(sentence) + 1 <= max_chars:
                current_chunk += " " + sentence if current_chunk else sentence
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                # If single sentence is too long, split by words
                if len(sentence) > max_chars:
                    words = sentence.split()
                    word_chunk = ""
                    for word in words:
                        if len(word_chunk) + len(word) + 1 <= max_chars:
                            word_chunk += " " + word if word_chunk else word
                        else:
                            if word_chunk:
                                chunks.append(word_chunk)
                            word_chunk = word
                    if word_chunk:
                        current_chunk = word_chunk
                else:
                    current_chunk = sentence
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks if chunks else [text]

    def _split_into_sentences(self, text: str) -> List[str]:
        """Simple sentence splitting by punctuation."""
        # Split by sentence-ending punctuation
        sentences = re.split(r'([.!?]+[\s\n]+)', text)
        result = []
        for i in range(0, len(sentences) - 1, 2):
            sentence = sentences[i]
            if i + 1 < len(sentences):
                sentence += sentences[i + 1]
            if sentence.strip():
                result.append(sentence.strip())
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())
        return result if result else [text]

    def _process_chunks_parallel(
        self,
        text_chunks: List[str],
        language: str,
        gpt_latent: object,
        speaker_embedding: object,
        inference_kwargs: Dict[str, object],
        max_workers: int,
    ) -> List[np.ndarray]:
        """Process text chunks in parallel using ThreadPoolExecutor."""
        start_time = time.time()
        self._logger.info("Processing %d chunks in parallel with %d workers", len(text_chunks), max_workers)
        
        # Create a function to process a single chunk
        def process_chunk(chunk_data: Tuple[int, str]) -> Tuple[int, np.ndarray]:
            import time
            chunk_idx, chunk_text = chunk_data
            chunk_start_time = time.time()
            worker_id = threading.current_thread().ident
            self._log(f"🔄 [Worker {worker_id}] Bắt đầu chunk {chunk_idx + 1}/{len(text_chunks)} ({len(chunk_text)} ký tự)")
            self._logger.info("[Worker %d] Starting chunk %d/%d (%d chars)", 
                            worker_id, chunk_idx + 1, len(text_chunks), len(chunk_text))
            try:
                chunk_audio = self._run_inference(
                    use_streaming=False,  # Parallel processing uses batch mode
                    text=chunk_text,
                    language=language,
                    gpt_cond_latent=gpt_latent,
                    speaker_embedding=speaker_embedding,
                    **inference_kwargs,
                )
                elapsed = time.time() - chunk_start_time
                self._log(f"✅ [Worker {worker_id}] Hoàn tất chunk {chunk_idx + 1}/{len(text_chunks)} trong {elapsed:.2f}s")
                self._logger.info("[Worker %d] Completed chunk %d/%d in %.2fs", 
                                worker_id, chunk_idx + 1, len(text_chunks), elapsed)
                return chunk_idx, chunk_audio
            except Exception as e:
                elapsed = time.time() - chunk_start_time
                error_msg = f"[Worker {worker_id}] Lỗi chunk {chunk_idx + 1}/{len(text_chunks)} sau {elapsed:.2f}s: {str(e)}"
                self._log(error_msg, "error")
                self._logger.error("[Worker %d] Failed chunk %d/%d after %.2fs: %s", 
                                 worker_id, chunk_idx + 1, len(text_chunks), elapsed, e)
                raise
        
        # Process chunks in parallel
        audio_results: Dict[int, np.ndarray] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all chunks
            future_to_chunk = {
                executor.submit(process_chunk, (i, chunk)): i 
                for i, chunk in enumerate(text_chunks)
            }
            
            # Collect results as they complete
            completed = 0
            errors = []
            total_chunks = len(text_chunks)
            for future in as_completed(future_to_chunk):
                try:
                    chunk_idx, chunk_audio = future.result()
                    audio_results[chunk_idx] = chunk_audio
                    completed += 1
                    elapsed = time.time() - start_time
                    remaining = total_chunks - completed
                    avg = elapsed / completed if completed else 0
                    eta = avg * remaining if remaining > 0 else 0
                    self._log(
                        f"📊 Tiến độ: {completed}/{total_chunks} chunks | "
                        f"đã chạy {elapsed:.2f}s, ước còn ~{eta:.2f}s"
                    )
                    self._logger.info(
                        "Completed chunk %d/%d (elapsed %.2fs, eta %.2fs)",
                        completed,
                        total_chunks,
                        elapsed,
                        eta,
                    )
                except Exception as e:
                    chunk_idx = future_to_chunk[future]
                    error_msg = f"Lỗi khi xử lý chunk {chunk_idx + 1}/{len(text_chunks)}: {str(e)}"
                    self._log(error_msg, "error")
                    self._logger.error("Error processing chunk %d: %s", chunk_idx + 1, e, exc_info=True)
                    errors.append(error_msg)
                    # Cancel remaining futures
                    for f in future_to_chunk:
                        if not f.done():
                            f.cancel()
            
            # If there were errors, raise with detailed message
            if errors:
                error_summary = "\n".join(errors)
                raise RuntimeError(
                    f"Xử lý audio thất bại:\n{error_summary}\n\n"
                    "Có thể do:\n"
                    "- Text quá dài cho một chunk\n"
                    "- Lỗi model inference\n"
                    "- Thiếu bộ nhớ\n"
                    "Thử giảm số workers hoặc chia nhỏ text hơn."
                )
        
        # Reconstruct audio chunks in original order
        audio_chunks = [audio_results[i] for i in range(len(text_chunks))]
        total_time = time.time() - start_time
        self._log(f"🎉 Tất cả {len(text_chunks)} chunks hoàn tất trong {total_time:.2f}s (xử lý song song)")
        self._logger.info("All %d chunks completed in %.2fs (parallel processing)", len(text_chunks), total_time)
        return audio_chunks

