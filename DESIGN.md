# TweenForge — Design Document

## Overview

TweenForge is an AI-powered tool that generates inbetween frames for 2D animation. It takes two key frames drawn by an animator and produces smooth intermediate frames, drastically reducing the manual labor of inbetweening.

The system runs as a **local HTTP server** with a **built-in web companion app**. The animator opens `http://localhost:9817` in their browser alongside their drawing tool (Clip Studio Paint, Photoshop, Krita, Procreate — anything that can export PNGs). For remote use, the same server deploys as a **cloud service**.

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
4. Work with **any** drawing application — no proprietary plugin APIs required
5. Produce editable output — animators can touch up generated frames

## Non-Goals

- Real-time preview (acceptable to take seconds per frame)
- Full animation pipeline (we only do inbetweening, not key pose generation)
- Style transfer or colorization
- Video interpolation for live-action footage

---

## Architecture

```
┌──────────────────────┐
│ Any Drawing App      │       ┌──────────────────────────────────────┐
│ (CSP, PS, Krita...)  │       │ Browser: http://localhost:9817       │
│                      │  PNG  │                                      │
│  Export key frames ──┼──────▶│  ┌──────────────────────────────┐   │
│  Import results    ◀─┼───────│  │  TweenForge Web Companion    │   │
│                      │  PNG  │  │  • Drag-and-drop frame upload │   │
└──────────────────────┘       │  │  • Settings (easing, count)  │   │
                               │  │  • Preview strip + playback  │   │
                               │  │  • Download generated frames │   │
                               │  └──────────────┬───────────────┘   │
                               └─────────────────┼───────────────────┘
                                                  │
                                        fetch() to same origin
                                                  │
                               ┌──────────────────▼───────────────────┐
                               │     TweenForge Server (Python)        │
                               │                                       │
                               │  GET  /              → Web UI         │
                               │  POST /interpolate/upload → generate  │
                               │  POST /interpolate   → native (CLI)   │
                               │  GET  /health        → status         │
                               │                                       │
                               │  ┌─────────────────────────────────┐  │
                               │  │ RIFE v4 Interpolation Engine    │  │
                               │  │ → Optical flow estimation       │  │
                               │  │ → Frame synthesis               │  │
                               │  │ → Line art post-processing      │  │
                               │  └─────────────────────────────────┘  │
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

### 2. Why a web companion app instead of a native plugin?

Clip Studio Paint has no JavaScript scripting API, no HTML panel system, and no open plugin SDK for animation timeline manipulation. Its only extensibility for third-party tools is file I/O (export/import PNG). Photoshop has UXP but it's complex and PS-only. Rather than fight each app's proprietary plugin system:

1. **A web app works with every drawing tool.** CSP, Photoshop, Krita, Procreate, even paper+scanner. If you can export a PNG, you can use TweenForge.
2. **Zero installation friction.** The server already runs on localhost — serving a web UI from it costs nothing. The animator just opens a browser tab.
3. **Cloud mode for free.** The same server deploys to a cloud instance. The web UI works identically whether it's localhost or a remote URL.

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
├── Drawing App (CSP, Photoshop, Krita, etc.)
├── Browser → http://localhost:9817 (TweenForge Web UI)
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
├── Drawing App                       ├── TweenForge Server
└── Browser ──────────HTTP──────────▶ ├── Web UI
                                      └── RIFE model (GPU instance)
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

## User Experience

### Web Companion Workflow

The web UI served at `http://localhost:9817` follows a **upload-generate-preview-download** workflow:

```
┌──────────────────────────────────────────────────────────────┐
│  UPLOAD           CONFIGURE         PREVIEW        DOWNLOAD  │
│                                                              │
│  Drag-and-drop →  Set count,    →  Thumbnail   →  Save PNGs │
│  two key frame    easing,          strip with      back to   │
│  PNGs             lineart mode     playback        disk      │
│                                                              │
│                       ↑                │                     │
│                       └── adjust ──────┘                     │
└──────────────────────────────────────────────────────────────┘
```

Key UX decisions:
- **Works with any drawing app.** CSP, Photoshop, Krita, Procreate — anything that exports PNGs. No proprietary plugin APIs needed.
- **Drag-and-drop upload.** The animator drags two exported PNGs into the browser. Thumbnails appear instantly for confirmation.
- **Nothing is committed until the user explicitly downloads.** Preview is non-destructive.
- **Thumbnail strip** shows all frames (key frames + generated) in sequence.
- **Inline playback** loops through the frames at ~8fps so the animator sees actual motion.
- **Adjust and regenerate** — change settings and re-generate without re-uploading.
- **Individual or bulk download** — save specific frames or all at once.

### Server Endpoints

| Endpoint | Purpose | Used by |
|---|---|---|
| `GET /` | Web companion UI | Browser |
| `POST /interpolate/upload` | Multipart upload → base64 PNGs | Web UI, cloud clients |
| `POST /interpolate/preview` | File-path based with thumbnails | Advanced integrations |
| `POST /interpolate` | File-path based, no thumbnails | CLI, batch processing |
| `GET /health` | Status + device info | Connection indicator |

### Why Not a Native Plugin?

| App | Plugin API Status | Problem |
|---|---|---|
| **Clip Studio Paint** | No scripting API, no HTML panels, C++ filter SDK only | Cannot programmatically access the animation timeline |
| **Photoshop** | UXP panels exist | Works, but PS-only; complex setup |
| **Krita** | Python scripting | Could work; Krita-only |
| **Procreate** | No plugin API | Impossible |

The web companion sidesteps all of these. An experimental Photoshop UXP plugin is included in `photoshop_plugin/` for teams that want tighter PS integration.

**CLI fallback** also works without any UI: `tweenforge generate frameA.png frameB.png -n 3`

---

## Data Flow

### Web Companion Workflow (Step by Step)

```
1. Animator draws Key Frame A and Key Frame B in their drawing app
2. Animator exports both as PNGs (File > Export in any app)
3. Animator opens http://localhost:9817 in their browser
4. Web UI checks server health → green dot shows device (cpu/cuda/mps)
5. Animator drags frame_A.png and frame_B.png into the drop zones
   → Thumbnails appear for visual confirmation
6. Animator sets: 3 inbetweens, ease-in-out, lineart cleanup ON
7. Animator clicks "Generate Preview"
8. Browser uploads both PNGs via POST /interpolate/upload
9. Server runs RIFE at t=0.25, t=0.5, t=0.75
10. Server applies line art post-processing
11. Server responds with base64-encoded PNGs
12. Web UI renders preview strip: [Key A] [tw 1] [tw 2] [tw 3] [Key B]
13. Animator clicks play → frames loop at ~8fps to judge motion
14. If bad: adjust settings → click "Regenerate" → goto 8
15. If good: click "Download All" → saves inbetween_000.png through _002.png
16. Animator imports the PNGs into their drawing app (File > Import)
17. Animator touches up frames as needed
```

### Cloud Mode

Same workflow, but the animator opens `https://your-server:9817` instead of localhost. The web UI is identical.

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
├── pyproject.toml                      # Project metadata and dependencies
├── DESIGN.md                           # This file
├── README.md                           # User-facing documentation
│
├── src/tweenforge/                     # Python package
│   ├── __init__.py
│   ├── config.py                       # Configuration management
│   ├── cli.py                          # CLI: serve, setup, generate
│   ├── engine/
│   │   ├── base.py                     # Interpolator ABC, easing math, data classes
│   │   ├── rife.py                     # RIFE model wrapper + weight download
│   │   └── postprocess.py              # Line art cleanup pipeline
│   ├── server/
│   │   ├── app.py                      # FastAPI — /, /interpolate, /upload, /health
│   │   ├── schemas.py                  # Pydantic request/response models
│   │   └── static/
│   │       └── index.html              # Web companion UI (drag-drop, preview, download)
│   ├── client/                         # Programmatic client SDK
│   │   ├── adapter.py                  # HostAdapter ABC for native integrations
│   │   ├── session.py                  # Workflow state machine
│   │   └── protocol.py                 # Shared data types
│   └── csp/
│       └── bridge.py                   # Config generation helpers
│
├── photoshop_plugin/                   # Experimental Photoshop UXP plugin
│   ├── manifest.json                   # UXP plugin manifest
│   ├── index.js                        # Photoshop adapter
│   └── panel.html                      # Panel loader
│
├── docker/
│   ├── Dockerfile                      # Production image with model weights
│   └── docker-compose.yml              # One-command cloud deployment
│
└── tests/
    ├── conftest.py                     # Shared fixtures (sample frames)
    ├── test_engine.py                  # Unit tests for interpolation + post-processing
    └── test_server.py                  # Integration tests for API endpoints
```

---

## Future Work

### Done
- ~~Web companion UI~~ — drag-and-drop upload, preview strip, inline playback, download
- ~~Preview before commit~~ — nothing touches disk until the user downloads
- ~~App-agnostic~~ — works with any tool that exports PNGs

### Short-term
- **PyInstaller bundle** — single executable for non-technical users
- **Batch mode** — interpolate multiple frame ranges in one request
- **Watch folder** — auto-detect new key frames dropped into a folder, generate without manual upload
- **ZIP download** — bundle all generated frames into a single .zip

### Medium-term
- **FILM integration** — alternative model for scenes with large motion
- **Multi-layer support** — process lineart, color, and shading layers independently
- **Stroke-aware interpolation** — vectorize line art, match strokes between frames, interpolate control points for pixel-perfect lines
- **Partial region selection** — only interpolate a selected area of the frame
- **Krita plugin** — Krita has a Python scripting API that could automate the export/import round-trip

### Long-term
- **Custom-trained model** — fine-tune on animation inbetween datasets (AnimeInterp, ATD-12K)
- **Topology-aware generation** — handle mouth shapes, eye blinks, hair physics
- **Style consistency** — maintain the artist's specific line quality and hatching patterns

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
