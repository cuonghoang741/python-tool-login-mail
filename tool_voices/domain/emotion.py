from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass(frozen=True)
class EmotionProfile:
    key: str
    label: str
    intensity_default: float = 0.5


def default_emotions() -> List[EmotionProfile]:
    return [
        EmotionProfile("neutral", "Neutral"),
        EmotionProfile("happy", "Happy / Joyful"),
        EmotionProfile("angry", "Angry"),
        EmotionProfile("sad", "Sad"),
        EmotionProfile("surprised", "Surprised"),
        EmotionProfile("afraid", "Afraid"),
    ]




