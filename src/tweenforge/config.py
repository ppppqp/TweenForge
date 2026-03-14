from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class TweenForgeConfig:
    host: str = "127.0.0.1"
    port: int = 9817
    model_dir: Path = field(default_factory=lambda: Path.home() / ".tweenforge" / "models")
    temp_dir: Path = field(default_factory=lambda: Path.home() / ".tweenforge" / "tmp")
    device: str = "auto"  # "auto", "cpu", "cuda", "mps"
    max_resolution: int = 4096
    default_easing: str = "linear"

    def __post_init__(self):
        self.model_dir = Path(self.model_dir)
        self.temp_dir = Path(self.temp_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls) -> TweenForgeConfig:
        return cls(
            host=os.getenv("TWEENFORGE_HOST", "127.0.0.1"),
            port=int(os.getenv("TWEENFORGE_PORT", "9817")),
            model_dir=Path(os.getenv("TWEENFORGE_MODEL_DIR", Path.home() / ".tweenforge" / "models")),
            temp_dir=Path(os.getenv("TWEENFORGE_TEMP_DIR", Path.home() / ".tweenforge" / "tmp")),
            device=os.getenv("TWEENFORGE_DEVICE", "auto"),
        )

    def resolve_device(self) -> str:
        if self.device != "auto":
            return self.device
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
            if torch.backends.mps.is_available():
                return "mps"
        except ImportError:
            pass
        return "cpu"
