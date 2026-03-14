import numpy as np
import pytest

from tweenforge.engine.base import (
    EasingType,
    InterpolationRequest,
    compute_easing_timestamps,
)
from tweenforge.engine.postprocess import LineArtPostProcessor, PostProcessConfig
from tweenforge.engine.rife import RIFEInterpolator


class TestEasingTimestamps:
    def test_linear_single(self):
        ts = compute_easing_timestamps(1, EasingType.LINEAR)
        assert len(ts) == 1
        assert ts[0] == pytest.approx(0.5)

    def test_linear_three(self):
        ts = compute_easing_timestamps(3, EasingType.LINEAR)
        assert len(ts) == 3
        assert ts == pytest.approx([0.25, 0.5, 0.75])

    def test_ease_in_biases_toward_start(self):
        ts = compute_easing_timestamps(3, EasingType.EASE_IN)
        # ease_in: t^2 — values should be smaller than linear
        linear = compute_easing_timestamps(3, EasingType.LINEAR)
        for t, l in zip(ts, linear):
            assert t <= l

    def test_ease_out_biases_toward_end(self):
        ts = compute_easing_timestamps(3, EasingType.EASE_OUT)
        linear = compute_easing_timestamps(3, EasingType.LINEAR)
        for t, l in zip(ts, linear):
            assert t >= l

    def test_ease_in_out_symmetric(self):
        ts = compute_easing_timestamps(3, EasingType.EASE_IN_OUT)
        assert ts[1] == pytest.approx(0.5)  # midpoint unchanged


class TestRIFEInterpolator:
    def test_is_available(self):
        interp = RIFEInterpolator(device="cpu")
        # Should be True if torch is installed
        assert interp.is_available() is True

    def test_interpolate_produces_correct_count(self, sample_frame_a, sample_frame_b):
        interp = RIFEInterpolator(device="cpu")
        req = InterpolationRequest(
            frame_a=sample_frame_a,
            frame_b=sample_frame_b,
            num_inbetweens=3,
        )
        result = interp.interpolate(req)
        assert len(result.frames) == 3
        assert len(result.timestamps) == 3

    def test_interpolate_frame_shape(self, sample_frame_a, sample_frame_b):
        interp = RIFEInterpolator(device="cpu")
        req = InterpolationRequest(
            frame_a=sample_frame_a,
            frame_b=sample_frame_b,
            num_inbetweens=1,
        )
        result = interp.interpolate(req)
        assert result.frames[0].shape == sample_frame_a.shape

    def test_midpoint_is_blend_of_inputs(self, sample_frame_a, sample_frame_b):
        """Without a trained model loaded, RIFE falls back to linear blend.
        The midpoint should be visually between the two inputs."""
        interp = RIFEInterpolator(device="cpu")
        req = InterpolationRequest(
            frame_a=sample_frame_a,
            frame_b=sample_frame_b,
            num_inbetweens=1,
        )
        result = interp.interpolate(req)
        mid = result.frames[0].astype(float)
        a = sample_frame_a.astype(float)
        b = sample_frame_b.astype(float)

        # Midpoint should be closer to the average than to either endpoint
        avg = (a + b) / 2
        dist_to_avg = np.mean(np.abs(mid - avg))
        dist_to_a = np.mean(np.abs(mid - a))
        assert dist_to_avg < dist_to_a


class TestPostProcessor:
    def test_binarize(self):
        # Gray frame should become black or white
        gray_frame = np.full((10, 10, 3), 128, dtype=np.uint8)
        pp = LineArtPostProcessor(PostProcessConfig(binarize=True, binarize_threshold=128))
        result = pp.process(gray_frame)
        unique = np.unique(result)
        assert set(unique).issubset({0, 255})

    def test_preserves_alpha(self):
        frame = np.full((10, 10, 4), 128, dtype=np.uint8)
        frame[:, :, 3] = 200  # custom alpha
        pp = LineArtPostProcessor(PostProcessConfig(preserve_alpha=True))
        result = pp.process(frame)
        assert result.shape[2] == 4
        np.testing.assert_array_equal(result[:, :, 3], 200)

    def test_batch_processing(self, sample_frame_a, sample_frame_b):
        pp = LineArtPostProcessor()
        results = pp.process_batch([sample_frame_a, sample_frame_b])
        assert len(results) == 2
