import numpy as np
import pytest


@pytest.fixture
def sample_frame_a():
    """A simple 64x64 RGBA test frame — white background with a black circle on the left."""
    frame = np.full((64, 64, 4), 255, dtype=np.uint8)
    # Draw a filled circle at (16, 32)
    for y in range(64):
        for x in range(64):
            if (x - 16) ** 2 + (y - 32) ** 2 < 100:
                frame[y, x, :3] = 0
    return frame


@pytest.fixture
def sample_frame_b():
    """A simple 64x64 RGBA test frame — white background with a black circle on the right."""
    frame = np.full((64, 64, 4), 255, dtype=np.uint8)
    for y in range(64):
        for x in range(64):
            if (x - 48) ** 2 + (y - 32) ** 2 < 100:
                frame[y, x, :3] = 0
    return frame
