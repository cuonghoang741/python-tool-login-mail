"""Domain models for the voice tool."""

from .emotion import EmotionProfile, default_emotions
from .voice_profile import VoiceProfile

__all__ = ["EmotionProfile", "default_emotions", "VoiceProfile"]

