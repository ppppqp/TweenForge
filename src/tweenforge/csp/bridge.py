"""CSP Bridge — helper to generate the CSP plugin config and manage the handshake.

This module doesn't run inside CSP; it generates and manages the artifacts
that the CSP-side JavaScript plugin uses (config file, temp directories, etc.).
"""

from __future__ import annotations

import json
from pathlib import Path

from tweenforge.config import TweenForgeConfig


def generate_csp_config(config: TweenForgeConfig, output_path: Path | None = None) -> dict:
    """Write a JSON config file that the CSP JavaScript plugin reads
    to know where to send requests."""
    cfg = {
        "server_url": f"http://{config.host}:{config.port}",
        "temp_dir": str(config.temp_dir),
        "endpoints": {
            "interpolate": "/interpolate",
            "upload": "/interpolate/upload",
            "health": "/health",
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(cfg, indent=2))

    return cfg
