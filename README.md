# TweenForge

AI-powered inbetween frame generator for 2D animation in Clip Studio Paint.

TweenForge takes two key frames and generates smooth intermediate frames using [RIFE](https://github.com/hzwer/Practical-RIFE) (Real-Time Intermediate Flow Estimation). It runs as a local server that the CSP plugin talks to, or as a cloud service for animators without GPUs.

## Quick Start

### Install

```bash
# Clone and install
git clone https://github.com/yourname/tweenforge.git
cd tweenforge
pip install -e ".[dev]"

# Download RIFE model weights (~30MB)
tweenforge setup
```

### Use from CLI (no CSP needed)

```bash
# Generate 3 inbetweens between two key frames
tweenforge generate keyframe_01.png keyframe_05.png -n 3 -e ease_in_out -o ./output

# With line art cleanup
tweenforge generate keyframe_01.png keyframe_05.png -n 3 --lineart -o ./output
```

### Use with Clip Studio Paint

```bash
# 1. Start the server
tweenforge serve

# 2. In CSP: File > Script > Run Script... > select csp_plugin/tweenforge.js
# 3. Follow the prompts to select frames and generate inbetweens
```

### Use via Cloud

```bash
# Deploy with Docker
cd docker
docker compose up -d

# Or call the cloud endpoint directly
curl -X POST https://your-server:9817/interpolate/upload \
  -F "frame_a=@keyframe_01.png" \
  -F "frame_b=@keyframe_05.png" \
  -F "num_inbetweens=3" \
  -F "easing=ease_in_out"
```

## API

### `POST /interpolate` (native mode)

For local use — reads and writes files on disk.

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

### `POST /interpolate/upload` (cloud mode)

Multipart upload — for remote use.

- `frame_a`: PNG file
- `frame_b`: PNG file
- `num_inbetweens`: integer (1-24)
- `easing`: `linear` | `ease_in` | `ease_out` | `ease_in_out`
- `lineart_mode`: `true` | `false`

Returns base64-encoded PNGs in the response.

### `GET /health`

Server status and configuration.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## Architecture

See [DESIGN.md](DESIGN.md) for the full technical design, architecture decisions, and future roadmap.

## License

MIT
