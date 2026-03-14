# TweenForge — Design Document

## Overview

TweenForge is an AI-powered tool that generates inbetween frames for 2D animation in Clip Studio Paint (CSP). It takes two key frames drawn by an animator and produces smooth intermediate frames, drastically reducing the manual labor of inbetweening.

The system runs as a **local HTTP server** (native mode) or a **cloud-hosted service** (cloud mode), with a lightweight JavaScript plugin inside CSP that acts as the bridge.

---

## Problem

Traditional 2D animation requires animators to draw **key poses** and then manually create all the **inbetween frames** for smooth motion. For 24fps animation, a 1-second movement between two key poses requires drawing 22 inbetweens by hand. This is:

- **Time-consuming**: Inbetweening accounts for 60-70% of total animation production time
- **Repetitive**: Most inbetweens are mechanical interpolations that don't require creative decisions
- **Error-prone**: Maintaining consistent line weight, volume, and spacing across frames is difficult

## Goals

1. Generate usable inbetween frames from two key frames with minimal user input
2. Support both local (native) and cloud processing
3. Preserve line art quality — clean strokes, consistent weight, no blur artifacts
4. Integrate into the CSP workflow with minimal friction
5. Produce editable output — animators can touch up generated frames

## Non-Goals

- Real-time preview (acceptable to take seconds per frame)
- Full animation pipeline (we only do inbetweening, not key pose generation)
- Style transfer or colorization
- Video interpolation for live-action footage

---

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│                   Clip Studio Paint                       │
│                                                           │
│  ┌────────────┐     ┌───────────────────────────┐        │
│  │ Animation   │ ──▶ │ tweenforge.js (CSP Script) │        │
│  │ Timeline    │ ◀── │ • Export key frames as PNG  │        │
│  │             │     │ • Show settings dialog      │        │
│  │             │     │ • Import generated frames   │        │
│  └────────────┘     └──────────────┬────────────┘        │
└─────────────────────────────────────┼────────────────────┘
                                      │
                    HTTP POST to localhost:9817 (native)
                    or https://api.tweenforge.io (cloud)
                                      │
                                      ▼
              ┌───────────────────────────────────────┐
              │         TweenForge Server (Python)     │
              │                                        │
              │  POST /interpolate                     │
              │    → file-path based (native mode)     │
              │                                        │
              │  POST /interpolate/upload               │
              │    → multipart upload (cloud mode)      │
              │                                        │
              │  ┌──────────────────────────────────┐  │
              │  │ Interpolation Engine              │  │
              │  │  ┌────────────────┐               │  │
              │  │  │ RIFE v4 (IFNet)│               │  │
              │  │  │ Optical flow   │               │  │
              │  │  │ Frame synthesis│               │  │
              │  │  └────────────────┘               │  │
              │  │           │                        │  │
              │  │           ▼                        │  │
              │  │  ┌────────────────┐               │  │
              │  │  │ Post-Processor │               │  │
              │  │  │ • Binarize     │               │  │
              │  │  │ • Denoise      │               │  │
              │  │  │ • Line cleanup │               │  │
              │  │  └────────────────┘               │  │
              │  └──────────────────────────────────┘  │
              └───────────────────────────────────────┘
```

---

## Key Design Decisions

### 1. Why RIFE for interpolation?

We evaluated several approaches:

| Approach | Quality | Speed | Complexity | Chosen? |
|---|---|---|---|---|
| **Linear pixel blend** | Poor — ghosting | Instant | Trivial | No (baseline fallback only) |
| **Optical flow warp (OpenCV)** | Medium — tearing on large motion | Fast | Low | No |
| **RIFE v4** | Good — handles moderate motion well | ~100ms/frame (GPU) | Medium | **Yes** |
| **FILM** | Very good — better on large motion | ~500ms/frame (GPU) | Medium | Considered for future |
| **Custom diffusion model** | Best potential | Slow (~2s/frame) | Very high | Future work |
| **Stroke vectorization + spline interp** | Best for clean lines | Medium | Very high | Future work |

**RIFE wins** on the effort-to-quality ratio. Pre-trained weights are freely available (Apache-2.0), inference is fast enough for interactive use, and it handles the typical motion range in 2D animation well. It falls back to a linear blend when the model weights aren't available, which ensures the system always produces output.

### 2. Why a client-server architecture?

Three reasons:

1. **CSP's scripting environment is limited.** JavaScript in CSP cannot run PyTorch or load ML models. An external process is required.
2. **Separation of concerns.** The heavy ML inference runs in Python with full access to CUDA/MPS. The CSP plugin stays lightweight.
3. **Cloud mode for free.** The same FastAPI server runs locally or deployed to a cloud instance — no code changes. Animators without GPUs can use cloud inference.

### 3. Why two endpoints (`/interpolate` and `/interpolate/upload`)?

- **`/interpolate` (native):** Both CSP and the server are on the same machine. Frames are read/written via file paths. No network transfer of image data. Fastest option.
- **`/interpolate/upload` (cloud):** The server is remote. Frames are uploaded as multipart form data and results are returned as base64-encoded PNGs. Works from any machine with internet access.

### 4. Why easing support?

Animators don't want evenly-spaced inbetweens. In animation, motion follows easing curves (slow-in, slow-out) to feel natural. We compute non-uniform timestamps and pass them to the interpolation model, which generates frames at those temporal positions.

### 5. Why line art post-processing?

AI frame interpolation models are trained on natural video. They produce soft, anti-aliased blends that look fine for photos but produce muddy lines in animation. The post-processor:

- **Binarizes** the output to crisp black/white lines
- **Removes noise** — small pixel clusters from interpolation artifacts
- **Preserves alpha** — transparency data passes through untouched

This is a pragmatic solution. The long-term approach is a model fine-tuned specifically on animation line art.

---

## Native vs Cloud Mode

### Native Mode

```
Animator's Machine
├── Clip Studio Paint + tweenforge.js
└── TweenForge Server (Python process)
    └── RIFE model (loaded into GPU/CPU)
```

**Pros:**
- Zero latency on file I/O (shared filesystem)
- No internet required
- Full privacy — frames never leave the machine

**Cons:**
- Requires Python + PyTorch installed locally
- GPU recommended for usable speed
- Setup complexity for non-technical users

**Mitigation:** We bundle the server as a standalone executable via PyInstaller so users don't need to manage a Python environment.

### Cloud Mode

```
Animator's Machine                    Cloud Server
├── Clip Studio Paint     ──HTTP──▶  ├── TweenForge Server
└── tweenforge.js                    └── RIFE model (GPU instance)
```

**Pros:**
- No local GPU needed
- No Python installation required
- Accessible from any machine

**Cons:**
- Network latency (upload + download)
- Privacy concerns (frames sent to remote server)
- Operating cost for GPU instances

**Deployment:** Docker image provided. Deploy to any cloud with GPU support (AWS EC2 g5, GCP L4, etc.) or run on CPU for lighter workloads.

---

## CSP Plugin Limitations and Workarounds

Clip Studio Paint's scripting API (v2.x) is still maturing. Known limitations and our workarounds:

| Limitation | Workaround |
|---|---|
| No programmatic PNG export API | Use `executeMenuCommand("file_export_png")` — may require manual save dialog interaction |
| No direct animation cel creation API | Import as image layer, then manually assign to timeline cel |
| No HTTP client in CSP JavaScript | Use `XMLHttpRequest` (available in CSP's JS runtime) |
| Script UI limited to `prompt()`/`alert()` | Sufficient for MVP; future versions can use CSP's Dialog API |
| Cannot detect current frame number programmatically in all cases | User specifies frame numbers via prompt |

**Fallback workflow (if scripting is too limited):** The user manually exports key frames as PNGs, runs `tweenforge generate frameA.png frameB.png -n 3`, and manually imports the results. The CLI works independently of CSP.

---

## Data Flow

### Native Mode — Step by Step

```
1. User draws Key Frame A (frame 1) and Key Frame B (frame 5) in CSP
2. User runs tweenforge.js from Script menu
3. Script prompts: start frame, end frame, # inbetweens, easing, lineart mode
4. Script exports frame 1 → ~/.tweenforge/tmp/export_xxx/keyframe_0001.png
5. Script exports frame 5 → ~/.tweenforge/tmp/export_xxx/keyframe_0005.png
6. Script POSTs to http://127.0.0.1:9817/interpolate:
   {
     "frame_a_path": "~/.tweenforge/tmp/export_xxx/keyframe_0001.png",
     "frame_b_path": "~/.tweenforge/tmp/export_xxx/keyframe_0005.png",
     "num_inbetweens": 3,
     "easing": "ease_in_out",
     "lineart_mode": true,
     "output_dir": "~/.tweenforge/tmp/output_xxx/"
   }
7. Server loads both PNGs, runs RIFE at t=0.25, t=0.5, t=0.75
8. Server applies line art post-processing (binarize + denoise)
9. Server writes inbetween_000.png, inbetween_001.png, inbetween_002.png
10. Server responds with { "status": "complete", "frames": [...paths...] }
11. Script imports each PNG into CSP timeline at frames 2, 3, 4
12. Animator reviews and touches up as needed
```

### Cloud Mode — Step by Step

```
1-3. Same as native
4-5. Script reads frame PNGs into memory (or from temp export)
6. Script POSTs multipart form to https://api.tweenforge.io/interpolate/upload:
   - frame_a: <binary PNG>
   - frame_b: <binary PNG>
   - num_inbetweens: 3
   - easing: ease_in_out
   - lineart_mode: true
7-8. Same processing on the server side
9. Server responds with base64-encoded PNGs in JSON
10. Script decodes base64, writes to temp files
11-12. Same as native
```

---

## Performance Expectations

| Frame Size | Device | Time per Inbetween | Notes |
|---|---|---|---|
| 1920x1080 | NVIDIA RTX 3060 | ~80ms | Comfortable for interactive use |
| 1920x1080 | Apple M2 (MPS) | ~200ms | Acceptable |
| 1920x1080 | CPU (8-core) | ~2s | Usable for small batches |
| 4096x2160 | NVIDIA RTX 3060 | ~300ms | May need tiling for VRAM |
| 4096x2160 | CPU | ~8s | Consider cloud mode |

---

## File Structure

```
tweenforge/
├── pyproject.toml              # Project metadata and dependencies
├── DESIGN.md                   # This file
├── README.md                   # User-facing documentation
├── src/tweenforge/
│   ├── __init__.py
│   ├── config.py               # Configuration management
│   ├── cli.py                  # CLI: serve, setup, generate
│   ├── engine/
│   │   ├── base.py             # Interpolator ABC, easing math, data classes
│   │   ├── rife.py             # RIFE model wrapper + weight download
│   │   └── postprocess.py      # Line art cleanup pipeline
│   ├── server/
│   │   ├── app.py              # FastAPI — /interpolate, /interpolate/upload, /health
│   │   └── schemas.py          # Pydantic request/response models
│   └── csp/
│       └── bridge.py           # Generates config JSON for the CSP plugin
├── csp_plugin/
│   └── tweenforge.js           # CSP-side JavaScript plugin
├── docker/
│   ├── Dockerfile              # Production image with model weights baked in
│   └── docker-compose.yml      # One-command cloud deployment
└── tests/
    ├── conftest.py             # Shared fixtures (sample frames)
    ├── test_engine.py          # Unit tests for interpolation + post-processing
    └── test_server.py          # Integration tests for API endpoints
```

---

## Future Work

### Short-term
- **PyInstaller bundle** — single executable for non-technical users
- **CSP Dialog UI** — replace `prompt()`/`alert()` with proper dialog panels
- **Batch mode** — interpolate multiple frame ranges in one request
- **Onion-skin preview** — show generated frames as semi-transparent overlays before committing

### Medium-term
- **FILM integration** — alternative model for scenes with large motion
- **Multi-layer support** — process lineart, color, and shading layers independently
- **Stroke-aware interpolation** — vectorize line art, match strokes between frames, interpolate control points for pixel-perfect lines
- **Partial region selection** — only interpolate a selected area of the frame

### Long-term
- **Custom-trained model** — fine-tune on animation inbetween datasets (AnimeInterp, ATD-12K)
- **Topology-aware generation** — handle mouth shapes, eye blinks, hair physics
- **Style consistency** — maintain the artist's specific line quality and hatching patterns
- **Real-time preview** — generate low-res previews instantly, refine on demand

---

## Security Considerations

- **Native mode** binds to `127.0.0.1` by default — not accessible from the network
- **Cloud mode** (`--cloud` flag) binds to `0.0.0.0` — should be deployed behind a reverse proxy with authentication
- File path endpoints (`/interpolate`) are disabled in cloud mode in production to prevent arbitrary file reads
- Uploaded images are validated (PIL.Image.open will reject non-image data)
- Temp files are written to a dedicated directory and should be cleaned up periodically

---

## Dependencies

| Package | Purpose | License |
|---|---|---|
| FastAPI | HTTP server framework | MIT |
| uvicorn | ASGI server | BSD-3 |
| Pillow | Image I/O | HPND |
| NumPy | Array operations | BSD-3 |
| PyTorch | ML inference runtime | BSD-3 |
| torchvision | Image transforms | BSD-3 |
| Pydantic | Data validation | MIT |
| Click | CLI framework | BSD-3 |
| RIFE v4 weights | Pre-trained model | Apache-2.0 |
