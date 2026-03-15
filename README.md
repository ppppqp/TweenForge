# TweenForge

AI-powered inbetween frame generator for 2D animation.

TweenForge takes two key frames and generates smooth intermediate frames using [RIFE](https://github.com/hzwer/Practical-RIFE) (Real-Time Intermediate Flow Estimation). It works with **any drawing app** — Clip Studio Paint, Photoshop, Krita, Procreate, or anything else that can export PNGs.

## How It Works

1. Export two key frames from your drawing app as PNGs
2. Open `http://localhost:9817` in your browser
3. Drag-and-drop the PNGs, pick settings, click Generate
4. Preview the result with inline playback
5. Download the generated frames and import back into your app

## Quick Start

### Install

```bash
git clone https://github.com/ppppqp/TweenForge.git
cd TweenForge
pip install -e ".[dev]"

# Download RIFE model weights (~30MB)
tweenforge setup
```

### Web UI (recommended)

```bash
# Start the server — opens web UI at http://localhost:9817
tweenforge serve
```

Then open [http://localhost:9817](http://localhost:9817) in your browser.

### CLI (no browser needed)

```bash
# Generate 3 inbetweens between two key frames
tweenforge generate keyframe_01.png keyframe_05.png -n 3 -e ease_in_out -o ./output

# With line art cleanup
tweenforge generate keyframe_01.png keyframe_05.png -n 3 --lineart -o ./output
```

### Cloud Deployment

```bash
cd docker
docker compose up -d
# Web UI available at http://your-server:9817
```

## API

### `POST /interpolate/upload`

Multipart upload — used by the web UI and remote clients.

- `frame_a`: PNG file
- `frame_b`: PNG file
- `num_inbetweens`: integer (1-24)
- `easing`: `linear` | `ease_in` | `ease_out` | `ease_in_out`
- `lineart_mode`: `true` | `false`

Returns base64-encoded PNGs in the response.

### `POST /interpolate` (native mode)

For local file-path-based workflows (CLI, scripts).

```json
{
  "frame_a_path": "/path/to/frame_01.png",
  "frame_b_path": "/path/to/frame_05.png",
  "num_inbetweens": 3,
  "easing": "ease_in_out",
  "lineart_mode": true,
  "output_dir": "/path/to/output/"
}
```

### `GET /health`

Server status, device info, and model status.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Architecture

See [DESIGN.md](DESIGN.md) for the full technical design, architecture decisions, and future roadmap.

## License

MIT
