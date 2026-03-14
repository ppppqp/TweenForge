from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

import numpy as np


class EasingType(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


@dataclass
class InterpolationRequest:
    frame_a: np.ndarray  # H x W x C, uint8
    frame_b: np.ndarray  # H x W x C, uint8
    num_inbetweens: int = 1
    easing: EasingType = EasingType.LINEAR
    lineart_mode: bool = False  # enables line-art-specific post-processing


@dataclass
class InterpolationResult:
    frames: list[np.ndarray]  # list of H x W x C uint8 arrays
    timestamps: list[float]  # normalized [0,1] position of each generated frame


def compute_easing_timestamps(n: int, easing: EasingType) -> list[float]:
    """Compute n evenly-spaced timestamps between frame A (0) and frame B (1),
    then warp them according to the easing function."""
    raw = [(i + 1) / (n + 1) for i in range(n)]

    if easing == EasingType.LINEAR:
        return raw
    elif easing == EasingType.EASE_IN:
        return [t * t for t in raw]
    elif easing == EasingType.EASE_OUT:
        return [1 - (1 - t) ** 2 for t in raw]
    elif easing == EasingType.EASE_IN_OUT:
        return [
            2 * t * t if t < 0.5 else 1 - (-2 * t + 2) ** 2 / 2
            for t in raw
        ]
    return raw


class Interpolator(ABC):
    """Base class for frame interpolation engines."""

    @abstractmethod
    def interpolate(self, request: InterpolationRequest) -> InterpolationResult:
        """Generate inbetween frames from a pair of key frames."""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this interpolator's dependencies are satisfied."""
        ...
