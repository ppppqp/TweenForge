"""Session — the core workflow state machine shared across all host adapters.

The session drives the user through:
    idle → selecting → configuring → generating → previewing → importing
                                         ↑              │
                                         └──────────────┘  (adjust & regenerate)

This logic is host-agnostic. The HostAdapter handles all app-specific I/O.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import tempfile
from enum import Enum
from pathlib import Path

import httpx
import numpy as np
from PIL import Image

from tweenforge.client.adapter import HostAdapter
from tweenforge.client.protocol import GenerateRequest, PreviewFrame, PreviewResult

logger = logging.getLogger(__name__)

THUMBNAIL_SIZE = (192, 192)


class SessionState(str, Enum):
    IDLE = "idle"
    SELECTING = "selecting"
    CONFIGURING = "configuring"
    GENERATING = "generating"
    PREVIEWING = "previewing"
    IMPORTING = "importing"


def _make_thumbnail_b64(image_path: Path) -> str:
    img = Image.open(image_path)
    img.thumbnail(THUMBNAIL_SIZE, Image.Resampling.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


class Session:
    """Manages one inbetweening workflow cycle."""

    def __init__(self, adapter: HostAdapter, server_url: str = "http://127.0.0.1:9817"):
        self.adapter = adapter
        self.server_url = server_url.rstrip("/")
        self.state = SessionState.IDLE
        self._request: GenerateRequest | None = None
        self._preview: PreviewResult | None = None
        self._work_dir: Path | None = None
        self._exported_a: Path | None = None
        self._exported_b: Path | None = None

    @property
    def preview(self) -> PreviewResult | None:
        return self._preview

    def configure(self, request: GenerateRequest) -> None:
        """Set generation parameters. Can be called in IDLE or PREVIEWING state
        (to adjust and regenerate)."""
        self._request = request
        self.state = SessionState.CONFIGURING

    def generate(self) -> PreviewResult:
        """Export key frames, call the server, and return a preview.

        Does NOT import anything into the timeline yet — the user must
        explicitly call accept() after reviewing the preview.
        """
        if self._request is None:
            raise ValueError("Call configure() before generate()")

        self.state = SessionState.GENERATING
        req = self._request

        # Create a temp working directory for this session
        self._work_dir = Path(tempfile.mkdtemp(prefix="tweenforge_"))
        export_dir = self._work_dir / "export"
        output_dir = self._work_dir / "output"
        export_dir.mkdir()
        output_dir.mkdir()

        # Export key frames from the host app
        self.adapter.show_progress(0.1, "Exporting key frames...")
        self._exported_a = self.adapter.export_frame(
            req.frame_a_number, export_dir / f"key_{req.frame_a_number:04d}.png"
        )
        self._exported_b = self.adapter.export_frame(
            req.frame_b_number, export_dir / f"key_{req.frame_b_number:04d}.png"
        )

        # Generate thumbnails of key frames for the preview UI
        thumb_a = _make_thumbnail_b64(self._exported_a)
        thumb_b = _make_thumbnail_b64(self._exported_b)

        # Call the server
        self.adapter.show_progress(0.3, "Generating inbetweens...")
        try:
            result = self._call_server(output_dir)
        except Exception as e:
            self.state = SessionState.CONFIGURING
            return PreviewResult(status="error", error=str(e))

        self.adapter.show_progress(0.9, "Preparing preview...")

        # Build preview frames with thumbnails
        preview_frames = []
        for i, frame_path in enumerate(result.get("frames", [])):
            target_num = req.frame_a_number + i + 1
            thumb = _make_thumbnail_b64(Path(frame_path))
            preview_frames.append(PreviewFrame(
                index=i,
                target_frame_number=target_num,
                timestamp=result.get("timestamps", [])[i] if i < len(result.get("timestamps", [])) else 0,
                image_path=frame_path,
                thumbnail_base64=thumb,
            ))

        self._preview = PreviewResult(
            status="complete",
            frames=preview_frames,
            key_frame_a_thumbnail=thumb_a,
            key_frame_b_thumbnail=thumb_b,
        )

        self.adapter.show_progress(1.0, "Preview ready")
        self.state = SessionState.PREVIEWING
        return self._preview

    def accept(self) -> None:
        """Import the previewed frames into the host timeline."""
        if self.state != SessionState.PREVIEWING or self._preview is None:
            raise ValueError("No preview to accept. Call generate() first.")

        self.state = SessionState.IMPORTING
        frames = self._preview.frames

        self.adapter.show_progress(0.0, "Importing frames...")

        for i, pf in enumerate(frames):
            self.adapter.show_progress(
                (i + 1) / len(frames),
                f"Importing frame {pf.target_frame_number}..."
            )
            self.adapter.import_frame(Path(pf.image_path), pf.target_frame_number)

        self.adapter.show_notification(
            f"Imported {len(frames)} inbetween frame(s).", level="info"
        )
        self.state = SessionState.IDLE
        self._preview = None

    def reject(self) -> None:
        """Discard the preview and return to configuring state."""
        self._preview = None
        self.state = SessionState.CONFIGURING

    def _call_server(self, output_dir: Path) -> dict:
        """Call the TweenForge server's native interpolation endpoint."""
        payload = {
            "frame_a_path": str(self._exported_a),
            "frame_b_path": str(self._exported_b),
            "num_inbetweens": self._request.num_inbetweens,
            "easing": self._request.easing,
            "lineart_mode": self._request.lineart_mode,
            "output_dir": str(output_dir),
        }

        resp = httpx.post(f"{self.server_url}/interpolate", json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "complete":
            raise RuntimeError(data.get("error", "Server returned non-complete status"))

        return data
