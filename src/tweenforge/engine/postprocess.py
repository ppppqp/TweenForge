"""Post-processing pipeline for interpolated frames.

AI interpolation often produces soft/blurry edges. For line art animation,
we need crisp, consistent strokes. This module provides filters to clean up
the output.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass
class PostProcessConfig:
    binarize: bool = True
    binarize_threshold: int = 128
    denoise_kernel_size: int = 3
    min_stroke_area: int = 4
    preserve_alpha: bool = True


class LineArtPostProcessor:
    """Clean up interpolated line art frames."""

    def __init__(self, config: PostProcessConfig | None = None):
        self.config = config or PostProcessConfig()

    def process(self, frame: np.ndarray) -> np.ndarray:
        """Apply the full post-processing pipeline to a single frame.

        Args:
            frame: H x W x C uint8 array (RGB or RGBA)

        Returns:
            Cleaned frame with same shape and dtype
        """
        has_alpha = frame.shape[2] == 4
        if has_alpha and self.config.preserve_alpha:
            alpha = frame[:, :, 3:]
            rgb = frame[:, :, :3]
        else:
            alpha = None
            rgb = frame[:, :, :3]

        gray = np.mean(rgb, axis=2)

        if self.config.binarize:
            gray = self._binarize(gray)

        if self.config.denoise_kernel_size > 1:
            gray = self._remove_small_components(gray)

        # Convert back to RGB
        result = np.stack([gray, gray, gray], axis=2).astype(np.uint8)

        if alpha is not None:
            result = np.concatenate([result, alpha], axis=2)

        return result

    def _binarize(self, gray: np.ndarray) -> np.ndarray:
        """Threshold grayscale to black/white."""
        binary = np.where(gray < self.config.binarize_threshold, 0, 255).astype(np.uint8)
        return binary

    def _remove_small_components(self, binary: np.ndarray) -> np.ndarray:
        """Remove small isolated pixel clusters (noise from interpolation).

        Uses a simple box-filter approach: if a pixel's neighborhood average
        doesn't agree with its value, flip it. This is faster than connected
        component analysis and sufficient for post-interpolation cleanup.
        """
        k = self.config.denoise_kernel_size
        pad = k // 2

        padded = np.pad(binary, pad, mode="edge")
        h, w = binary.shape

        # Compute local mean via cumulative sums for speed
        neighborhood_sum = np.zeros_like(binary, dtype=np.float64)
        for di in range(k):
            for dj in range(k):
                neighborhood_sum += padded[di:di + h, dj:dj + w].astype(np.float64)

        neighborhood_mean = neighborhood_sum / (k * k)

        # If a black pixel's neighborhood is mostly white, remove it (noise)
        result = binary.copy()
        noise_black = (binary == 0) & (neighborhood_mean > 200)
        noise_white = (binary == 255) & (neighborhood_mean < 55)
        result[noise_black] = 255
        result[noise_white] = 0

        return result

    def process_batch(self, frames: list[np.ndarray]) -> list[np.ndarray]:
        return [self.process(f) for f in frames]
