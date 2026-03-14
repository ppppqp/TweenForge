"""TweenForge CLI — local server, model setup, and one-shot interpolation."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from tweenforge import __version__

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


@click.group()
@click.version_option(__version__)
def main():
    """TweenForge — AI-powered inbetween frame generator."""


@main.command()
@click.option("--host", default="127.0.0.1", help="Bind address")
@click.option("--port", default=9817, type=int, help="Port number")
@click.option("--device", default="auto", help="Compute device: auto, cpu, cuda, mps")
@click.option("--cloud", is_flag=True, help="Bind to 0.0.0.0 for cloud/remote access")
def serve(host: str, port: int, device: str, cloud: bool):
    """Start the TweenForge HTTP server."""
    import os

    import uvicorn

    os.environ["TWEENFORGE_DEVICE"] = device
    if cloud:
        host = "0.0.0.0"
        logger.info("Cloud mode: binding to 0.0.0.0")

    os.environ["TWEENFORGE_HOST"] = host
    os.environ["TWEENFORGE_PORT"] = str(port)

    logger.info("Starting TweenForge server on %s:%d (device=%s)", host, port, device)
    uvicorn.run("tweenforge.server.app:app", host=host, port=port, reload=False)


@main.command()
def setup():
    """Download RIFE model weights."""
    from tweenforge.engine.rife import RIFEInterpolator

    logger.info("Downloading RIFE model weights...")
    path = RIFEInterpolator.download_model()
    logger.info("Model ready at %s", path)


@main.command()
@click.argument("frame_a", type=click.Path(exists=True))
@click.argument("frame_b", type=click.Path(exists=True))
@click.option("-n", "--num", default=1, type=int, help="Number of inbetweens to generate")
@click.option("-e", "--easing", default="linear", type=click.Choice(["linear", "ease_in", "ease_out", "ease_in_out"]))
@click.option("-o", "--output-dir", default=".", type=click.Path())
@click.option("--lineart", is_flag=True, help="Apply line art post-processing")
@click.option("--device", default="auto", help="Compute device")
def generate(frame_a: str, frame_b: str, num: int, easing: str, output_dir: str, lineart: bool, device: str):
    """Generate inbetween frames from two key frames (offline, no server needed)."""
    import numpy as np
    from PIL import Image

    from tweenforge.config import TweenForgeConfig
    from tweenforge.engine.base import EasingType, InterpolationRequest
    from tweenforge.engine.postprocess import LineArtPostProcessor
    from tweenforge.engine.rife import RIFEInterpolator

    cfg = TweenForgeConfig.from_env()
    cfg.device = device
    resolved_device = cfg.resolve_device()

    logger.info("Loading frames...")
    img_a = np.array(Image.open(frame_a).convert("RGBA"))
    img_b = np.array(Image.open(frame_b).convert("RGBA"))

    interpolator = RIFEInterpolator(device=resolved_device, model_dir=cfg.model_dir)

    req = InterpolationRequest(
        frame_a=img_a,
        frame_b=img_b,
        num_inbetweens=num,
        easing=EasingType(easing),
        lineart_mode=lineart,
    )

    logger.info("Generating %d inbetween(s) on device=%s ...", num, resolved_device)
    result = interpolator.interpolate(req)

    frames = result.frames
    if lineart:
        frames = LineArtPostProcessor().process_batch(frames)

    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    for i, frame in enumerate(frames):
        path = out / f"inbetween_{i:03d}.png"
        Image.fromarray(frame).save(path)
        logger.info("Saved %s", path)

    logger.info("Done. Generated %d frame(s) in %s", len(frames), out)


if __name__ == "__main__":
    main()
