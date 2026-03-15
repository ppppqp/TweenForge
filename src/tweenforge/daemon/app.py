"""TweenForge Companion Daemon — global hotkey-driven workflow.

Runs as a background process alongside CSP (or any drawing app). Registers
a global hotkey and orchestrates:

    1st press  →  capture current canvas via clipboard  →  "Frame A captured"
    2nd press  →  capture canvas again                  →  generate inbetweens
    preview    →  Tkinter popup with playback           →  accept or reject
    accept     →  auto-import frames via clipboard paste + timeline navigation

State machine:

    IDLE ──(hotkey)──▶ CAPTURED_A ──(hotkey)──▶ GENERATING ──▶ PREVIEWING
                                                                 │    │
                                                           accept│    │reject
                                                                 ▼    ▼
                                                           IMPORTING  IDLE
                                                                 │
                                                                 ▼
                                                               IDLE
"""

from __future__ import annotations

import io
import logging
import tempfile
import threading
import time
from enum import Enum
from pathlib import Path

import httpx
import numpy as np
from PIL import Image
from pynput import keyboard

from tweenforge.daemon.capture import (
    capture_current_frame,
    navigate_timeline,
    paste_image_to_csp,
)
from tweenforge.daemon.preview import PreviewWindow

logger = logging.getLogger(__name__)


class State(str, Enum):
    IDLE = "idle"
    CAPTURED_A = "captured_a"
    GENERATING = "generating"
    PREVIEWING = "previewing"
    IMPORTING = "importing"


class CompanionDaemon:
    """The main daemon that listens for hotkeys and drives the workflow."""

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:9817",
        hotkey: str = "<ctrl>+<shift>+t",
        num_inbetweens: int = 3,
        easing: str = "ease_in_out",
        lineart_mode: bool = False,
    ):
        self.server_url = server_url.rstrip("/")
        self.hotkey_str = hotkey
        self.num_inbetweens = num_inbetweens
        self.easing = easing
        self.lineart_mode = lineart_mode

        self.state = State.IDLE
        self._work_dir = Path(tempfile.mkdtemp(prefix="tweenforge_daemon_"))
        self._frame_a_path: Path | None = None
        self._frame_b_path: Path | None = None
        self._generated_paths: list[Path] = []
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self):
        """Start listening for the global hotkey. Blocks."""
        logger.info("TweenForge Companion started")
        logger.info("  Hotkey: %s", self.hotkey_str)
        logger.info("  Server: %s", self.server_url)
        logger.info("  Settings: %d inbetweens, %s easing, lineart=%s",
                     self.num_inbetweens, self.easing, self.lineart_mode)
        logger.info("")
        logger.info("Switch to your drawing app and press %s to capture Frame A.", self.hotkey_str)

        self._listener = keyboard.GlobalHotKeys({
            self.hotkey_str: self._on_hotkey,
        })
        self._listener.start()

        # Keep main thread alive
        try:
            self._listener.join()
        except KeyboardInterrupt:
            logger.info("Companion stopped.")

    def stop(self):
        if self._listener:
            self._listener.stop()

    def _on_hotkey(self):
        """Called when the global hotkey is pressed."""
        if self.state == State.IDLE:
            self._capture_frame_a()
        elif self.state == State.CAPTURED_A:
            self._capture_frame_b()
        elif self.state in (State.GENERATING, State.PREVIEWING, State.IMPORTING):
            logger.info("Busy — please wait for the current operation to finish.")

    def _capture_frame_a(self):
        """Capture the current canvas as Frame A."""
        logger.info("Capturing Frame A...")

        path = self._work_dir / "frame_a.png"
        result = capture_current_frame(path)

        if result is None:
            logger.error("Failed to capture Frame A. Is your drawing app focused?")
            logger.error("Make sure the canvas is visible and try again.")
            return

        self._frame_a_path = result
        self.state = State.CAPTURED_A
        logger.info("Frame A captured: %s", result)
        logger.info("")
        logger.info("Now navigate to your end frame and press %s again.", self.hotkey_str)

    def _capture_frame_b(self):
        """Capture the current canvas as Frame B, then generate."""
        logger.info("Capturing Frame B...")

        path = self._work_dir / "frame_b.png"
        result = capture_current_frame(path)

        if result is None:
            logger.error("Failed to capture Frame B. Is your drawing app focused?")
            self.state = State.IDLE
            return

        self._frame_b_path = result
        logger.info("Frame B captured: %s", result)
        logger.info("")

        # Generate in a background thread so the hotkey listener stays responsive
        thread = threading.Thread(target=self._generate_and_preview, daemon=True)
        thread.start()

    def _generate_and_preview(self):
        """Call the server to generate inbetweens, then show preview."""
        self.state = State.GENERATING
        logger.info("Generating %d inbetween(s)...", self.num_inbetweens)

        try:
            generated = self._call_server()
        except Exception as e:
            logger.error("Generation failed: %s", e)
            self.state = State.IDLE
            return

        self._generated_paths = generated
        self.state = State.PREVIEWING

        logger.info("Generated %d frame(s). Opening preview...", len(generated))

        # Show preview window (blocks until user accepts/rejects)
        preview = PreviewWindow(
            frame_a_path=self._frame_a_path,
            frame_b_path=self._frame_b_path,
            generated_paths=generated,
            on_accept=self._on_accept,
            on_reject=self._on_reject,
        )
        preview.show()

    def _call_server(self) -> list[Path]:
        """Upload frames to the server and get generated inbetweens back."""
        with open(self._frame_a_path, "rb") as fa, open(self._frame_b_path, "rb") as fb:
            resp = httpx.post(
                f"{self.server_url}/interpolate/upload",
                files={
                    "frame_a": ("frame_a.png", fa, "image/png"),
                    "frame_b": ("frame_b.png", fb, "image/png"),
                },
                data={
                    "num_inbetweens": str(self.num_inbetweens),
                    "easing": self.easing,
                    "lineart_mode": str(self.lineart_mode).lower(),
                },
                timeout=120,
            )

        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "complete":
            raise RuntimeError(data.get("error", "Server returned error"))

        # Decode base64 frames and save to disk
        output_dir = self._work_dir / "output"
        output_dir.mkdir(exist_ok=True)

        paths = []
        import base64
        for i, b64 in enumerate(data["frames_base64"]):
            img_data = base64.b64decode(b64)
            img = Image.open(io.BytesIO(img_data))
            p = output_dir / f"inbetween_{i:03d}.png"
            img.save(p)
            paths.append(p)

        return paths

    def _on_accept(self):
        """User accepted the preview — import frames into CSP."""
        self.state = State.IMPORTING
        n = len(self._generated_paths)

        logger.info("Importing %d frame(s) into your drawing app...", n)
        logger.info("Please do not touch the keyboard/mouse for a few seconds.")

        # Give user a moment to read the log, then switch focus back to CSP
        time.sleep(1.0)

        # Strategy: the user is currently at Frame B's position.
        # We navigate backwards (n steps) to reach the first inbetween position,
        # then paste each frame moving forward.
        logger.info("Navigating back %d frame(s)...", n)
        navigate_timeline("left", steps=n)
        time.sleep(0.3)

        for i, frame_path in enumerate(self._generated_paths):
            logger.info("  Pasting frame %d/%d...", i + 1, n)
            paste_image_to_csp(frame_path)
            time.sleep(0.3)

            if i < n - 1:
                navigate_timeline("right", steps=1)
                time.sleep(0.2)

        logger.info("")
        logger.info("Done! %d inbetween frame(s) imported.", n)
        logger.info("You may need to adjust layer order or convert pasted layers to animation cels.")
        logger.info("")
        logger.info("Press %s to start a new capture.", self.hotkey_str)
        self.state = State.IDLE

    def _on_reject(self):
        """User rejected the preview."""
        logger.info("Preview discarded.")
        logger.info("Press %s to start a new capture.", self.hotkey_str)
        self.state = State.IDLE
