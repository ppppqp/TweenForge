"""Clipboard-based frame capture and paste.

Uses the system clipboard to grab the current CSP canvas (via simulated
Cmd+Shift+C / Ctrl+Shift+C) and to paste generated frames back (Cmd+V / Ctrl+V).

This avoids any reliance on CSP's non-existent scripting API. The only
requirement is that CSP is the focused window when the hotkey is pressed.
"""

from __future__ import annotations

import platform
import subprocess
import tempfile
import time
from pathlib import Path

import pyautogui
from PIL import Image, ImageGrab

SYSTEM = platform.system()  # "Darwin", "Windows", "Linux"

# Brief pause after simulating keypresses so the app can process
_KEY_DELAY = 0.15


def _modifier() -> str:
    """Return the platform modifier key name for pyautogui."""
    return "command" if SYSTEM == "Darwin" else "ctrl"


def copy_canvas_to_clipboard() -> None:
    """Simulate the 'Copy Merged' shortcut in CSP.

    CSP shortcut: Edit > Copy (merge visible layers)
    Default: Ctrl+Shift+C (Windows) / Cmd+Shift+C (macOS)
    """
    mod = _modifier()
    pyautogui.hotkey(mod, "shift", "c")
    time.sleep(_KEY_DELAY)


def grab_clipboard_image() -> Image.Image | None:
    """Read the current clipboard contents as a PIL Image."""
    time.sleep(0.1)  # allow clipboard to settle
    img = ImageGrab.grabclipboard()
    if isinstance(img, Image.Image):
        return img
    return None


def capture_current_frame(output_path: Path) -> Path | None:
    """Copy the CSP canvas to clipboard and save as PNG.

    Returns the path if successful, None if clipboard didn't contain an image.
    """
    copy_canvas_to_clipboard()
    time.sleep(0.3)  # CSP needs a moment to write to clipboard

    img = grab_clipboard_image()
    if img is None:
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, format="PNG")
    return output_path


def paste_image_to_csp(image_path: Path) -> None:
    """Copy an image to the system clipboard, then paste it into CSP.

    CSP interprets Ctrl/Cmd+V as "paste as new layer on the current frame".
    """
    _copy_image_to_clipboard(image_path)
    time.sleep(0.2)
    mod = _modifier()
    pyautogui.hotkey(mod, "v")
    time.sleep(_KEY_DELAY)


def navigate_timeline(direction: str, steps: int = 1) -> None:
    """Move the CSP timeline cursor left or right.

    Args:
        direction: "left" or "right"
        steps: number of frames to move
    """
    key = "left" if direction == "left" else "right"
    for _ in range(steps):
        pyautogui.press(key)
        time.sleep(0.05)
    time.sleep(_KEY_DELAY)


def _copy_image_to_clipboard(image_path: Path) -> None:
    """Platform-specific: copy a PNG file to the system clipboard."""
    if SYSTEM == "Darwin":
        # macOS: use osascript to copy image to clipboard
        script = f'''
        set the clipboard to (read POSIX file "{image_path}" as «class PNGf»)
        '''
        subprocess.run(["osascript", "-e", script], check=True, capture_output=True)

    elif SYSTEM == "Windows":
        # Windows: use PowerShell to copy image to clipboard
        ps_cmd = f'[System.Windows.Forms.Clipboard]::SetImage([System.Drawing.Image]::FromFile("{image_path}"))'
        subprocess.run(
            ["powershell", "-command",
             "Add-Type -AssemblyName System.Windows.Forms;" + ps_cmd],
            check=True, capture_output=True,
        )

    elif SYSTEM == "Linux":
        # Linux: use xclip
        subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "image/png", "-i", str(image_path)],
            check=True, capture_output=True,
        )
