"""Shared protocol types used by both the client session and the server.

These are plain dataclasses (not Pydantic) so they can be used in any context
including the JavaScript plugins via JSON serialization.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class GenerateRequest:
    """Parameters for an inbetween generation job."""
    frame_a_number: int
    frame_b_number: int
    num_inbetweens: int = 1
    easing: str = "linear"  # linear | ease_in | ease_out | ease_in_out
    lineart_mode: bool = False
    preview_scale: float = 1.0  # 0.25 = quarter res preview, 1.0 = full res

    def to_dict(self) -> dict:
        return {
            "frame_a_number": self.frame_a_number,
            "frame_b_number": self.frame_b_number,
            "num_inbetweens": self.num_inbetweens,
            "easing": self.easing,
            "lineart_mode": self.lineart_mode,
            "preview_scale": self.preview_scale,
        }


@dataclass
class PreviewFrame:
    """A single generated frame in a preview set."""
    index: int               # 0-based index within the inbetween set
    target_frame_number: int  # where this would be inserted in the timeline
    timestamp: float          # normalized position between key frames (0-1)
    image_path: str = ""     # local path (native mode)
    image_base64: str = ""   # base64 PNG (cloud mode)
    thumbnail_base64: str = ""  # small thumbnail for quick preview


@dataclass
class PreviewResult:
    """The full result of a generate-and-preview operation."""
    status: str  # "complete" | "error"
    frames: list[PreviewFrame] = field(default_factory=list)
    key_frame_a_thumbnail: str = ""  # base64 thumbnail of frame A
    key_frame_b_thumbnail: str = ""  # base64 thumbnail of frame B
    error: str = ""
