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
    error: str | None = None


class UploadInterpolateResponse(BaseModel):
    """Response for the cloud upload-based endpoint. Returns base64-encoded PNGs."""
    status: str
    frames_base64: list[str] = Field(default_factory=list)
    timestamps: list[float] = Field(default_factory=list)
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str
    device: str
    model_loaded: bool
