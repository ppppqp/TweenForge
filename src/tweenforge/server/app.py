"""FastAPI server — serves both native (local file-path) and cloud (upload) modes.

Native mode:  POST /interpolate          — reads/writes files on disk
              POST /interpolate/preview   — same but returns thumbnails for UI preview
Cloud mode:   POST /interpolate/upload    — accepts multipart uploads, returns base64 PNGs
Web UI:       GET  /                      — companion web app (upload, preview, download)
Health:       GET  /health
"""

from __future__ import annotations

import base64
import io
import logging
from pathlib import Path

import numpy as np
from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image

from tweenforge import __version__
from tweenforge.config import TweenForgeConfig
from tweenforge.engine.base import EasingType as EngineEasing
from tweenforge.engine.base import InterpolationRequest
from tweenforge.engine.postprocess import LineArtPostProcessor
from tweenforge.engine.rife import RIFEInterpolator
from tweenforge.server.schemas import (
    EasingType,
    HealthResponse,
    InterpolateRequest,
    InterpolateResponse,
    PreviewFrameInfo,
    PreviewRequest,
    PreviewResponse,
    UploadInterpolateResponse,
)

logger = logging.getLogger(__name__)

app = FastAPI(title="TweenForge", version=__version__)

# ---------------------------------------------------------------------------
# Web companion UI — served at /
# ---------------------------------------------------------------------------

_STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def web_ui():
    return FileResponse(_STATIC_DIR / "index.html")


# Lazy-initialized singletons
_config: TweenForgeConfig | None = None
_interpolator: RIFEInterpolator | None = None
_postprocessor: LineArtPostProcessor | None = None


def get_config() -> TweenForgeConfig:
    global _config
    if _config is None:
        _config = TweenForgeConfig.from_env()
    return _config


def get_interpolator() -> RIFEInterpolator:
    global _interpolator
    if _interpolator is None:
        cfg = get_config()
        device = cfg.resolve_device()
        _interpolator = RIFEInterpolator(device=device, model_dir=cfg.model_dir)
        logger.info("Interpolator initialized on device=%s", device)
    return _interpolator


def get_postprocessor() -> LineArtPostProcessor:
    global _postprocessor
    if _postprocessor is None:
        _postprocessor = LineArtPostProcessor()
    return _postprocessor


def _load_image(path: str) -> np.ndarray:
    img = Image.open(path).convert("RGBA")
    return np.array(img)


def _save_image(arr: np.ndarray, path: Path) -> None:
    Image.fromarray(arr).save(path)


def _make_thumbnail_b64(img: Image.Image | np.ndarray, size: int = 192) -> str:
    if isinstance(img, np.ndarray):
        img = Image.fromarray(img)
    img = img.copy()
    img.thumbnail((size, size), Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _to_engine_easing(e: EasingType) -> EngineEasing:
    return EngineEasing(e.value)


# ---------------------------------------------------------------------------
# Native mode endpoint — reads/writes files on local disk
# ---------------------------------------------------------------------------

@app.post("/interpolate", response_model=InterpolateResponse)
async def interpolate_native(req: InterpolateRequest):
    try:
        frame_a = _load_image(req.frame_a_path)
        frame_b = _load_image(req.frame_b_path)

        engine_req = InterpolationRequest(
            frame_a=frame_a,
            frame_b=frame_b,
            num_inbetweens=req.num_inbetweens,
            easing=_to_engine_easing(req.easing),
            lineart_mode=req.lineart_mode,
        )

        result = get_interpolator().interpolate(engine_req)
        frames = result.frames

        if req.lineart_mode:
            frames = get_postprocessor().process_batch(frames)

        out_dir = Path(req.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        paths = []
        for i, frame in enumerate(frames):
            p = out_dir / f"inbetween_{i:03d}.png"
            _save_image(frame, p)
            paths.append(str(p))

        return InterpolateResponse(
            status="complete", frames=paths, timestamps=result.timestamps,
        )

    except Exception as e:
        logger.exception("Interpolation failed")
        return InterpolateResponse(status="error", error=str(e))


# ---------------------------------------------------------------------------
# Preview endpoint — generates frames AND returns thumbnails for UI
# ---------------------------------------------------------------------------

@app.post("/interpolate/preview", response_model=PreviewResponse)
async def interpolate_preview(req: PreviewRequest):
    try:
        frame_a = _load_image(req.frame_a_path)
        frame_b = _load_image(req.frame_b_path)

        # Generate thumbnails of the input key frames
        thumb_a = _make_thumbnail_b64(frame_a, req.thumbnail_size)
        thumb_b = _make_thumbnail_b64(frame_b, req.thumbnail_size)

        engine_req = InterpolationRequest(
            frame_a=frame_a,
            frame_b=frame_b,
            num_inbetweens=req.num_inbetweens,
            easing=_to_engine_easing(req.easing),
            lineart_mode=req.lineart_mode,
        )

        result = get_interpolator().interpolate(engine_req)
        frames = result.frames

        if req.lineart_mode:
            frames = get_postprocessor().process_batch(frames)

        out_dir = Path(req.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        preview_frames = []
        for i, frame in enumerate(frames):
            p = out_dir / f"inbetween_{i:03d}.png"
            _save_image(frame, p)
            thumb = _make_thumbnail_b64(frame, req.thumbnail_size)
            preview_frames.append(PreviewFrameInfo(
                index=i,
                timestamp=result.timestamps[i],
                image_path=str(p),
                thumbnail_base64=thumb,
            ))

        return PreviewResponse(
            status="complete",
            frames=preview_frames,
            key_frame_a_thumb=thumb_a,
            key_frame_b_thumb=thumb_b,
        )

    except Exception as e:
        logger.exception("Preview generation failed")
        return PreviewResponse(status="error", error=str(e))


# ---------------------------------------------------------------------------
# Cloud mode endpoint — accepts uploaded images, returns base64 PNGs
# ---------------------------------------------------------------------------

@app.post("/interpolate/upload", response_model=UploadInterpolateResponse)
async def interpolate_upload(
    frame_a: UploadFile = File(..., description="First key frame PNG"),
    frame_b: UploadFile = File(..., description="Second key frame PNG"),
    num_inbetweens: int = Form(default=1, ge=1, le=24),
    easing: str = Form(default="linear"),
    lineart_mode: bool = Form(default=False),
):
    try:
        data_a = await frame_a.read()
        data_b = await frame_b.read()

        img_a = np.array(Image.open(io.BytesIO(data_a)).convert("RGBA"))
        img_b = np.array(Image.open(io.BytesIO(data_b)).convert("RGBA"))

        engine_req = InterpolationRequest(
            frame_a=img_a,
            frame_b=img_b,
            num_inbetweens=num_inbetweens,
            easing=_to_engine_easing(EasingType(easing)),
            lineart_mode=lineart_mode,
        )

        result = get_interpolator().interpolate(engine_req)
        frames = result.frames

        if lineart_mode:
            frames = get_postprocessor().process_batch(frames)

        frames_b64 = []
        for frame in frames:
            buf = io.BytesIO()
            Image.fromarray(frame).save(buf, format="PNG")
            frames_b64.append(base64.b64encode(buf.getvalue()).decode("ascii"))

        return UploadInterpolateResponse(
            status="complete",
            frames_base64=frames_b64,
            timestamps=result.timestamps,
        )

    except Exception as e:
        logger.exception("Upload interpolation failed")
        return UploadInterpolateResponse(status="error", error=str(e))


# ---------------------------------------------------------------------------
# Health / info
# ---------------------------------------------------------------------------

@app.get("/health", response_model=HealthResponse)
async def health():
    cfg = get_config()
    interp = get_interpolator()
    return HealthResponse(
        status="ok",
        version=__version__,
        device=cfg.resolve_device(),
        model_loaded=interp._net is not None,
    )
