"""Host adapter interface — the contract every tool plugin must implement.

Each supported application (CSP, Photoshop, etc.) provides a concrete adapter
that knows how to read/write frames and interact with that app's timeline.
The shared Session logic drives the workflow through this interface.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path


@dataclass
class FrameInfo:
    number: int
    has_content: bool  # True if this cel has actual drawn content
    label: str = ""    # Optional user-assigned label (e.g., "key", "breakdown")


@dataclass
class TimelineInfo:
    start_frame: int
    end_frame: int
    fps: float
    total_frames: int


class HostAdapter(ABC):
    """Abstract interface that each host application plugin implements."""

    # -- Frame access --------------------------------------------------------

    @abstractmethod
    def get_timeline_info(self) -> TimelineInfo:
        """Return the current timeline range and FPS."""
        ...

    @abstractmethod
    def get_frames_with_content(self) -> list[FrameInfo]:
        """Return a list of frames that have drawn content (non-empty cels)."""
        ...

    @abstractmethod
    def get_current_frame(self) -> int:
        """Return the currently selected frame number."""
        ...

    @abstractmethod
    def export_frame(self, frame_number: int, output_path: Path) -> Path:
        """Export a single frame as a PNG file.

        Args:
            frame_number: The timeline frame to export.
            output_path: Where to write the PNG.

        Returns:
            The actual path written (may differ if the adapter appends extension).
        """
        ...

    @abstractmethod
    def import_frame(self, image_path: Path, frame_number: int) -> None:
        """Import a PNG file as a new cel at the given frame position."""
        ...

    @abstractmethod
    def insert_empty_frames(self, after_frame: int, count: int) -> None:
        """Insert empty frames into the timeline to make room for inbetweens.

        This shifts existing frames forward. If the host app doesn't support
        this, the adapter should raise NotImplementedError.
        """
        ...

    # -- UI callbacks --------------------------------------------------------

    @abstractmethod
    def show_progress(self, percent: float, message: str) -> None:
        """Update a progress indicator. percent is 0.0 to 1.0."""
        ...

    @abstractmethod
    def show_notification(self, message: str, level: str = "info") -> None:
        """Show a transient notification. level: 'info', 'warning', 'error'."""
        ...

    @abstractmethod
    def request_frame_range(self) -> tuple[int, int] | None:
        """Ask the user to select a start and end frame.

        Returns (start, end) or None if cancelled. Implementations should
        provide a visual picker appropriate for the host app.
        """
        ...
