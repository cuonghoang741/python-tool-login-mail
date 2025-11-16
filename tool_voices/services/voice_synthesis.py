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
from typing import Dict, List, Optional, Tuple

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
    ) -> None:
        self._voice_clone_service = voice_clone_service
        self._gateway = gateway or XTTSModelGateway()
        self._repository = repository or VoiceRepository(Path("./voices"))
        self._output_dir: Path = (output_dir or Path("./outputs")).resolve()
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._logger = logging.getLogger(__name__)

    def synthesize(
        self,
        text: str,
        voice_name: str,
        emotion: str,
        intensity: float,
        output_path: Optional[Path] = None,
        max_workers: int = 1,
        advanced_params: Optional[Dict[str, object]] = None,
    ) -> Path:
        if not text.strip():
            raise ValueError("Văn bản đầu vào không được để trống.")

        voice = self._load_voice(voice_name)
        language = self._select_language(voice, text)
        destination = output_path or self._build_output_path(voice_name, emotion)

        gpt_latent, speaker_embedding = self._load_conditionings(voice)
        inference_kwargs = self._prepare_inference_kwargs(
            emotion, intensity, advanced_params or {}
        )
        
        # Check if text needs to be split into chunks
        text_chunks = self._split_text_into_chunks(text, language)
        
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
            audio = self._run_inference(
                text=text_chunks[0],
                language=language,
                gpt_cond_latent=gpt_latent,
                speaker_embedding=speaker_embedding,
                **inference_kwargs,
            )
        else:
            # Process multiple chunks in parallel and concatenate
            sample_rate = self._resolve_sample_rate()
            
            # Use parallel processing if max_workers > 1
            # Note: With lock, parallel processing may not be much faster, but still useful for I/O bound operations
            if max_workers > 1 and len(text_chunks) > 1:
                try:
                    audio_chunks = self._process_chunks_parallel(
                        text_chunks,
                        language,
                        gpt_latent,
                        speaker_embedding,
                        inference_kwargs,
                        max_workers,
                    )
                except Exception as e:
                    self._logger.error("Parallel processing failed, falling back to sequential: %s", e)
                    # Fallback to sequential processing on error
                    audio_chunks = []
                    for i, chunk in enumerate(text_chunks):
                        self._logger.info("Processing chunk %d/%d (%d chars)", i + 1, len(text_chunks), len(chunk))
                        chunk_audio = self._run_inference(
                            text=chunk,
                            language=language,
                            gpt_cond_latent=gpt_latent,
                            speaker_embedding=speaker_embedding,
                            **inference_kwargs,
                        )
                        audio_chunks.append(chunk_audio)
            else:
                # Sequential processing
                audio_chunks = []
                for i, chunk in enumerate(text_chunks):
                    self._logger.info("Processing chunk %d/%d (%d chars)", i + 1, len(text_chunks), len(chunk))
                    chunk_audio = self._run_inference(
                        text=chunk,
                        language=language,
                        gpt_cond_latent=gpt_latent,
                        speaker_embedding=speaker_embedding,
                        **inference_kwargs,
                    )
                    audio_chunks.append(chunk_audio)
            
            # Concatenate all audio chunks in order
            audio = np.concatenate(audio_chunks)
            self._logger.info("Concatenated %d audio chunks into final audio", len(audio_chunks))
        
        sample_rate = self._resolve_sample_rate()
        self._write_wav(audio, sample_rate, destination)
        self._logger.info("Audio written to %s", destination)
        return destination

    def _load_voice(self, voice_name: str) -> VoiceProfile:
        voice = self._repository.load_voice(voice_name)
        if voice is None:
            raise ValueError(f"Giọng '{voice_name}' không tồn tại.")
        return voice

    def _load_conditionings(self, voice: VoiceProfile) -> Tuple[object, object]:
        torch = self._gateway.torch
        # Check embedding_path properly (avoid array comparison issues)
        has_embedding = voice.embedding_path is not None
        if has_embedding:
            try:
                embedding_exists = voice.embedding_path.exists()
            except (AttributeError, TypeError):
                # If embedding_path is not a Path-like object, treat as missing
                embedding_exists = False
        else:
            embedding_exists = False
            
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
        return gpt_latent, speaker_embedding

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

    def _run_inference(self, **kwargs: object) -> np.ndarray:
        """Run inference. PyTorch models in eval mode are generally thread-safe for inference."""
        tts_model = self._gateway.tts.synthesizer.tts_model
        # PyTorch models in eval() mode are generally thread-safe for inference
        # Each inference call is independent and doesn't modify model weights
        # If errors occur, we'll catch and handle them
        result = tts_model.inference(**kwargs)
        if isinstance(result, dict):
            # Avoid using 'or' with arrays/tensors - check explicitly
            audio = result.get("wav")
            if audio is None:
                audio = result.get("audio")
        else:
            audio = result
        
        # Check if audio is None properly (avoid array comparison)
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
        destination.parent.mkdir(parents=True, exist_ok=True)
        clipped = np.clip(data, -1.0, 1.0)
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

    def _split_text_into_chunks(self, text: str, language: str) -> List[str]:
        """Split text into chunks that fit within XTTS token limit (400 tokens)."""
        try:
            tts_model = self._gateway.tts.synthesizer.tts_model
            if not hasattr(tts_model, 'tokenizer') or tts_model.tokenizer is None:
                # Fallback: use character-based splitting
                return self._split_text_by_chars(text, max_chars=800)
            
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
                try:
                    tokens = tokenizer.encode(sentence, lang=language)
                    # tokenizer.encode returns a list of token IDs
                    if isinstance(tokens, (list, tuple)):
                        token_count = len(tokens)
                    elif hasattr(tokens, '__len__'):
                        token_count = len(tokens)
                    else:
                        token_count = len(sentence) // 2.5
                except Exception:
                    # Fallback: estimate ~1 token per 2-3 characters
                    token_count = len(sentence) // 2.5
                
                # If single sentence exceeds limits, split it further
                if token_count > safe_max_tokens or sentence_chars > safe_char_limit:
                    # Split long sentence by words
                    words = sentence.split()
                    word_chunk = ""
                    word_tokens = 0
                    word_chars = 0
                    
                    for word in words:
                        word_len = len(word)
                        try:
                            word_token_list = tokenizer.encode(word, lang=language)
                            word_token_count = len(word_token_list) if isinstance(word_token_list, (list, tuple)) else len(word) // 2.5
                        except Exception:
                            word_token_count = len(word) // 2.5
                        
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
            return self._split_text_by_chars(text, max_chars=800)

    def _split_text_by_chars(self, text: str, max_chars: int = 800) -> List[str]:
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
            start_time = time.time()
            self._logger.info("[Worker %d] Starting chunk %d/%d (%d chars)", 
                            threading.current_thread().ident, chunk_idx + 1, len(text_chunks), len(chunk_text))
            try:
                chunk_audio = self._run_inference(
                    text=chunk_text,
                    language=language,
                    gpt_cond_latent=gpt_latent,
                    speaker_embedding=speaker_embedding,
                    **inference_kwargs,
                )
                elapsed = time.time() - start_time
                self._logger.info("[Worker %d] Completed chunk %d/%d in %.2fs", 
                                threading.current_thread().ident, chunk_idx + 1, len(text_chunks), elapsed)
                return chunk_idx, chunk_audio
            except Exception as e:
                elapsed = time.time() - start_time
                self._logger.error("[Worker %d] Failed chunk %d/%d after %.2fs: %s", 
                                 threading.current_thread().ident, chunk_idx + 1, len(text_chunks), elapsed, e)
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
            for future in as_completed(future_to_chunk):
                try:
                    chunk_idx, chunk_audio = future.result()
                    audio_results[chunk_idx] = chunk_audio
                    completed += 1
                    self._logger.info("Completed chunk %d/%d", completed, len(text_chunks))
                except Exception as e:
                    chunk_idx = future_to_chunk[future]
                    error_msg = f"Lỗi khi xử lý chunk {chunk_idx + 1}/{len(text_chunks)}: {str(e)}"
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
        self._logger.info("All %d chunks completed in %.2fs (parallel processing)", len(text_chunks), total_time)
        return audio_chunks

