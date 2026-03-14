FROM python:3.11-slim AS base

WORKDIR /app

# Install system deps for Pillow and torch
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
COPY src/ ./src/

# Install with cloud extras
RUN pip install --no-cache-dir ".[cloud]"

# Download model weights at build time so the image is self-contained
RUN python -c "from tweenforge.engine.rife import RIFEInterpolator; RIFEInterpolator.download_model()"

EXPOSE 9817

CMD ["tweenforge", "serve", "--cloud", "--device", "cpu"]
