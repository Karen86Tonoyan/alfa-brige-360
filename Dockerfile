# ═══════════════════════════════════════════════════════════════════════════
# ALFA_CORE_KERNEL v3.0 — PRODUCTION DOCKERFILE
# ═══════════════════════════════════════════════════════════════════════════
# Multi-stage build dla optymalizacji rozmiaru
# WOLF-KING BLACK CONTAINER
# ═══════════════════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────────────
# STAGE 1: Builder
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS builder

# System dependencies for building
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    g++ \
    libffi-dev \
    libssl-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create virtual environment
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install Python dependencies
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip wheel && \
    pip install --no-cache-dir -r /tmp/requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# STAGE 2: Runtime
# ─────────────────────────────────────────────────────────────────────────────
FROM python:3.11-slim-bookworm AS runtime

# Metadata
LABEL maintainer="Karen86Tonoyan"
LABEL version="3.0"
LABEL description="ALFA_CORE_KERNEL — WOLF-KING Production Runtime"

# Runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    # OpenCV dependencies
    libgl1-mesa-glx \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libfontconfig1 \
    # Audio/Video
    ffmpeg \
    # General
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Copy virtual environment from builder
COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Security: Create non-root user
RUN groupadd -r alfa && useradd -r -g alfa alfa

# Working directory
WORKDIR /app

# Copy application
COPY --chown=alfa:alfa . /app/

# Create directories with proper permissions
RUN mkdir -p /app/storage/gemini_mirror \
             /app/storage/chunk_cache \
             /app/logs \
             /app/data/memory \
             /app/data/vault \
    && chown -R alfa:alfa /app/storage /app/logs /app/data

# Environment
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    TZ=Europe/Warsaw \
    ALFA_ENV=production \
    ALFA_LOG_LEVEL=INFO

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# Switch to non-root user
USER alfa

# Expose port
EXPOSE 8000

# Default command
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
