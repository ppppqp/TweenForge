from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class EasingType(str, Enum):
    LINEAR = "linear"
    EASE_IN = "ease_in"
    EASE_OUT = "ease_out"
    EASE_IN_OUT = "ease_in_out"


class InterpolateRequest(BaseModel):
    """Request body for the file-path-based interpolation endpoint (native mode)."""
    frame_a_path: str = Field(..., description="Absolute path to the first key frame image")
    frame_b_path: str = Field(..., description="Absolute path to the second key frame image")
    num_inbetweens: int = Field(default=1, ge=1, le=24)
    easing: EasingType = EasingType.LINEAR
    lineart_mode: bool = Field(default=False, description="Apply line art post-processing")
    output_dir: str = Field(..., description="Directory to write generated frames into")


class InterpolateResponse(BaseModel):
    status: str  # "complete" | "error"
    frames: list[str] = Field(default_factory=list, description="Paths to generated frame files")
    timestamps: list[float] = Field(default_factory=list)
    error: str | None = None


class UploadInterpolateResponse(BaseModel):
    """Response for the cloud upload-based endpoint. Returns base64-encoded PNGs."""
    status: str
    frames_base64: list[str] = Field(default_factory=list)
    timestamps: list[float] = Field(default_factory=list)
    error: str | None = None


class PreviewRequest(BaseModel):
    """Like InterpolateRequest but returns thumbnails + base64 for quick preview."""
    frame_a_path: str
    frame_b_path: str
    num_inbetweens: int = Field(default=1, ge=1, le=24)
    easing: EasingType = EasingType.LINEAR
    lineart_mode: bool = False
    output_dir: str
    thumbnail_size: int = Field(default=192, description="Max thumbnail dimension in pixels")


class PreviewFrameInfo(BaseModel):
    index: int
    timestamp: float
    image_path: str
    thumbnail_base64: str  # small base64 PNG for quick UI display


class PreviewResponse(BaseModel):
    status: str
    frames: list[PreviewFrameInfo] = Field(default_factory=list)
    key_frame_a_thumb: str = ""  # base64 thumbnail of input frame A
    key_frame_b_thumb: str = ""  # base64 thumbnail of input frame B
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    device: str
    model_loaded: bool
