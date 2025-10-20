FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim

# Create a group and user with a specific uid and gid
RUN groupadd -g 1000 m3u && useradd -u 1000 -g m3u -d /app -s /bin/bash m3u

WORKDIR /app

# Install runtime dependencies (ffmpeg for media processing)
RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg aubio-tools && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy application code, scripts, and station identity with proper ownership
COPY --chown=m3u:m3u src /app/src
COPY --chown=m3u:m3u scripts /app/scripts
COPY --chown=m3u:m3u station-identity.example.md /app/station-identity.md

# Create output directories
RUN mkdir -p /app/playlists /app/logs && chown -R m3u:m3u /app

# Metadata labels for best practices
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG REPO_URL

LABEL maintainer="troy@troykelly.com" \
  org.opencontainers.image.title="M3U to AzuraCast" \
  org.opencontainers.image.description="Extracts media from Emby and syncs to AzuraCast" \
  org.opencontainers.image.authors="Troy Kelly <troy@troykellycom>" \
  org.opencontainers.image.vendor="Troy Kelly" \
  org.opencontainers.image.licenses="Apache 2.0" \
  org.opencontainers.image.url="${REPO_URL}" \
  org.opencontainers.image.source="${REPO_URL}" \
  org.opencontainers.image.version="${VERSION}" \
  org.opencontainers.image.revision="${VCS_REF}" \
  org.opencontainers.image.created="${BUILD_DATE}"

# Add healthcheck for AI playlist module
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD python -c "import src.ai_playlist" || exit 1

# Switch to non-root user
USER m3u

CMD ["python", "src/main.py"]
