# TweenForge — Design Document

## Overview

TweenForge is an AI-powered tool that generates inbetween frames for 2D animation. It takes two key frames drawn by an animator and produces smooth intermediate frames, drastically reducing the manual labor of inbetweening.

The system runs as a **local HTTP server** (native mode) or a **cloud-hosted service** (cloud mode). Host application plugins (Clip Studio Paint, Photoshop, etc.) share a common UI panel and communicate with the server through a standardized **HostBridge adapter interface**.

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

## User Experience & Plugin Architecture

### The UX Problem (and what we fixed)

Early versions used `prompt()`/`alert()` dialogs — the worst possible UX for animators who work visually. The redesigned UX follows a **generate-preview-accept** workflow:

```
┌─────────────────────────────────────────────────────────┐
│  SELECT         CONFIGURE         PREVIEW       IMPORT  │
│                                                         │
│  Pick start  →  Set count,    →  See all     →  One     │
│  and end        easing,          frames with     click   │
│  frames         lineart mode     playback        import  │
│                                                         │
│                     ↑                │                   │
│                     └── adjust ──────┘                   │
└─────────────────────────────────────────────────────────┘
```

Key UX decisions:
- **Nothing is imported until the user explicitly accepts.** Preview is non-destructive.
- **Thumbnail strip** shows all frames (key frames + generated) in sequence so the animator can judge motion.
- **Inline playback** loops through the frames at ~8fps so the animator sees actual motion, not static thumbnails.
- **Adjust and regenerate** — if the result is bad, change settings and re-generate without leaving the panel.
- **Progress feedback** — real progress bar and status text, not a spinning cursor.

### HostBridge Adapter Pattern

Every host application (CSP, Photoshop, future tools) implements the same JavaScript interface:

```
HostBridge {
    getServerUrl()                    → string
    getTempDir()                      → string
    exportFrame(frameNum, outPath)    → Promise<string>
    importFrame(imagePath, frameNum)  → Promise<void>
    onReady()                         → void
}
```

The **panel UI is shared** — a single `panel.html` with all layout, styles, and interaction logic. Each host adapter injects its `HostBridge` implementation before the panel loads. This means:

1. **One UI to maintain** — visual changes propagate to all host apps automatically.
2. **Adding a new host** requires only writing a new adapter (~100 lines) — no UI work.
3. **The panel works standalone** (without a host) for debugging — it just skips the export/import calls.

```
csp_plugin/
├── tweenforge.js       ← CSP-specific HostBridge (export via CSP API)
└── panel.html          ← Shared UI (the single source of truth)

photoshop_plugin/
├── manifest.json       ← UXP plugin manifest
├── index.js            ← Photoshop-specific HostBridge (export via UXP API)
└── panel.html          ← Loads the shared panel.html
```

### Server Endpoints for the UX

| Endpoint | Purpose | Used by |
|---|---|---|
| `POST /interpolate/preview` | Generate frames AND return thumbnails for the UI | Panel preview workflow |
| `POST /interpolate` | Generate frames only (no thumbnails) | CLI, batch processing |
| `POST /interpolate/upload` | Multipart upload → base64 response | Cloud mode |
| `GET /health` | Status check with device info | Panel connection indicator |

The `/interpolate/preview` endpoint is what enables the preview UX — it returns small base64 thumbnails alongside the full-resolution output files, so the panel can render the preview strip instantly without loading large images.

---

## Host Plugin Limitations and Workarounds

### Clip Studio Paint

| Limitation | Workaround |
|---|---|
| No programmatic PNG export API | Use `doc.exportImage()` where available; fall back to `executeMenuCommand()` |
| No direct animation cel creation API | Import as image layer, then assign to timeline cel |
| HTML panel support varies by version | Fall back to CLI workflow for older CSP versions |
| Cannot detect current frame number in all cases | User specifies frame numbers in panel inputs |

### Photoshop

| Limitation | Workaround |
|---|---|
| No native animation timeline in all editions | Use video timeline layers; fall back to layer-based workflow |
| UXP panels can't load cross-origin scripts | Inline the shared panel.html at build time |
| `executeAsModal` required for document changes | All export/import wrapped in modal execution context |

**Universal fallback:** The CLI (`tweenforge generate`) works without any host app. Animators can manually export frames, run the CLI, and import results.

---

## Data Flow

### Interactive Panel Workflow (Native Mode)

```
1. Animator opens TweenForge panel in CSP/Photoshop
2. Panel checks server health → shows green/red connection dot
3. Animator types start frame (1) and end frame (5) in the panel
4. Animator sets: 3 inbetweens, ease-in-out, lineart cleanup ON
5. Animator clicks "Generate Preview"
6. Panel calls HostBridge.exportFrame() for frames 1 and 5
   → Adapter exports to ~/.tweenforge/tmp/export_xxx/
7. Panel POSTs to /interpolate/preview with paths + settings
8. Server generates 3 frames, creates thumbnails, writes full-res PNGs
9. Server responds with thumbnail base64 data + file paths
10. Panel renders preview strip: [Key A] [tw 1] [tw 2] [tw 3] [Key B]
11. Animator clicks play → frames loop at 8fps to judge motion
12. If bad: animator adjusts settings → click "Generate Preview" again → goto 7
13. If good: animator clicks "Import to Timeline"
14. Panel calls HostBridge.importFrame() for each generated frame
15. Frames appear in the host app's timeline at positions 2, 3, 4
```

### Cloud Mode

Same as above, but:
- Panel uploads frames via `POST /interpolate/upload` instead of file paths
- Server returns base64 PNGs in the response body
- Panel writes base64 data to temp files before calling `HostBridge.importFrame()`

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
├── pyproject.toml                  # Project metadata and dependencies
├── DESIGN.md                       # This file
├── README.md                       # User-facing documentation
│
├── src/tweenforge/                 # Python package
│   ├── __init__.py
│   ├── config.py                   # Configuration management
│   ├── cli.py                      # CLI: serve, setup, generate
│   ├── engine/
│   │   ├── base.py                 # Interpolator ABC, easing math, data classes
│   │   ├── rife.py                 # RIFE model wrapper + weight download
│   │   └── postprocess.py          # Line art cleanup pipeline
│   ├── server/
│   │   ├── app.py                  # FastAPI — /interpolate, /preview, /upload, /health
│   │   └── schemas.py              # Pydantic request/response models
│   ├── client/                     # Cross-tool client SDK (Python-side)
│   │   ├── adapter.py              # HostAdapter ABC — the contract for all host plugins
│   │   ├── session.py              # Workflow state machine (select→generate→preview→import)
│   │   └── protocol.py             # Shared data types (GenerateRequest, PreviewResult, etc.)
│   └── csp/
│       └── bridge.py               # Generates config JSON for host plugins
│
├── csp_plugin/                     # Clip Studio Paint plugin
│   ├── tweenforge.js               # CSP HostBridge adapter
│   └── panel.html                  # Shared UI (HTML/CSS/JS — used by all host plugins)
│
├── photoshop_plugin/               # Adobe Photoshop UXP plugin
│   ├── manifest.json               # UXP plugin manifest
│   ├── index.js                    # Photoshop HostBridge adapter
│   └── panel.html                  # Loads the shared panel.html
│
├── docker/
│   ├── Dockerfile                  # Production image with model weights baked in
│   └── docker-compose.yml          # One-command cloud deployment
│
└── tests/
    ├── conftest.py                 # Shared fixtures (sample frames)
    ├── test_engine.py              # Unit tests for interpolation + post-processing
    └── test_server.py              # Integration tests for API endpoints
```

---

## Future Work

### Done
- ~~CSP Dialog UI~~ — replaced `prompt()`/`alert()` with HTML panel UI
- ~~Preview before import~~ — thumbnail strip with inline playback
- ~~Cross-tool extensibility~~ — HostBridge adapter pattern, Photoshop plugin skeleton

### Short-term
- **PyInstaller bundle** — single executable for non-technical users
- **Batch mode** — interpolate multiple frame ranges in one request
- **Onion-skin overlay** — semi-transparent generated frames overlaid on the canvas for fine-tuning
- **Build script** — inline shared panel.html into each host plugin at build time

### Medium-term
- **FILM integration** — alternative model for scenes with large motion
- **Multi-layer support** — process lineart, color, and shading layers independently
- **Stroke-aware interpolation** — vectorize line art, match strokes between frames, interpolate control points for pixel-perfect lines
- **Partial region selection** — only interpolate a selected area of the frame
- **After Effects / Krita adapters** — additional host plugins using the same HostBridge pattern

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
