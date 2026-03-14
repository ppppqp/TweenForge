import io

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from tweenforge.server.app import app


@pytest.fixture
def client():
    return TestClient(app)


def _make_png_bytes(color: tuple[int, int, int, int]) -> bytes:
    img = Image.new("RGBA", (32, 32), color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


class TestHealthEndpoint:
    def test_health(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestUploadEndpoint:
    def test_upload_interpolation(self, client):
        frame_a = _make_png_bytes((0, 0, 0, 255))
        frame_b = _make_png_bytes((255, 255, 255, 255))

        resp = client.post(
            "/interpolate/upload",
            files={
                "frame_a": ("a.png", frame_a, "image/png"),
                "frame_b": ("b.png", frame_b, "image/png"),
            },
            data={
                "num_inbetweens": "2",
                "easing": "linear",
                "lineart_mode": "false",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert len(data["frames_base64"]) == 2
        assert len(data["timestamps"]) == 2

    def test_upload_lineart_mode(self, client):
        frame_a = _make_png_bytes((50, 50, 50, 255))
        frame_b = _make_png_bytes((200, 200, 200, 255))

        resp = client.post(
            "/interpolate/upload",
            files={
                "frame_a": ("a.png", frame_a, "image/png"),
                "frame_b": ("b.png", frame_b, "image/png"),
            },
            data={
                "num_inbetweens": "1",
                "easing": "ease_in_out",
                "lineart_mode": "true",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "complete"
        assert len(data["frames_base64"]) == 1
