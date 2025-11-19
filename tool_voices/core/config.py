from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict


@dataclass
class AppConfig:
    model_id: str = "tts_models/multilingual/multi-dataset/xtts_v2"
    use_gpu: bool = False
    voices_dir: str = "voices"
    outputs_dir: str = "outputs"
    logs_dir: str = "logs"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AppConfig":
        return cls(
            model_id=data.get("model_id", cls.model_id),
            use_gpu=bool(data.get("use_gpu", cls.use_gpu)),
            voices_dir=data.get("voices_dir", cls.voices_dir),
            outputs_dir=data.get("outputs_dir", cls.outputs_dir),
            logs_dir=data.get("logs_dir", cls.logs_dir),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ConfigManager:
    """Manage application configuration persisted to disk."""

    def __init__(self, root: Path | None = None) -> None:
        self._root = root or Path(".")
        self._config_path = self._root / "config" / "app.json"
        self._config_path.parent.mkdir(parents=True, exist_ok=True)
        self._config = AppConfig()
        self._load()

    @property
    def config(self) -> AppConfig:
        return self._config

    @property
    def voices_dir(self) -> Path:
        path = (self._root / self._config.voices_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def outputs_dir(self) -> Path:
        path = (self._root / self._config.outputs_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def logs_dir(self) -> Path:
        path = (self._root / self._config.logs_dir).resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path

    @property
    def model_id(self) -> str:
        return self._config.model_id

    @property
    def use_gpu(self) -> bool:
        return self._config.use_gpu

    def save(self) -> None:
        with self._config_path.open("w", encoding="utf-8") as handle:
            json.dump(self._config.to_dict(), handle, indent=2)

    def _load(self) -> None:
        if not self._config_path.exists():
            self.save()
            return
        with self._config_path.open("r", encoding="utf-8") as handle:
            data = json.load(handle)
        self._config = AppConfig.from_dict(data)







