FROM python:3.13-slim as builder

WORKDIR /app

# Install build dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

FROM python:3.13-slim

# Create a group and user with a specific uid and gid
RUN groupadd -g 1000 m3u && useradd -u 1000 -g m3u -d /app -s /bin/bash m3u

WORKDIR /app

# Install runtime dependencies (ffmpeg for media processing, cron for scheduling)
RUN apt-get update && \
  DEBIAN_FRONTEND=noninteractive apt-get install -y \
    ffmpeg \
    aubio-tools \
    cron \
    tzdata && \
  apt-get clean && \
  rm -rf /var/lib/apt/lists/*

# Copy Python packages from builder stage
COPY --from=builder /usr/local/lib/python3.13/site-packages /usr/local/lib/python3.13/site-packages

# Copy application code and scripts with proper ownership
COPY --chown=m3u:m3u src /app/src
COPY --chown=m3u:m3u scripts /app/scripts
COPY --chown=m3u:m3u station-identity.md /app/station-identity.md

# Create necessary directories with proper ownership
RUN mkdir -p /app/playlists /app/logs && \
  chown -R m3u:m3u /app

# Set up cron job for Saturday at 1am (local time)
# The cron job runs the AI playlist generation and deployment
RUN echo "0 1 * * 6 cd /app && /usr/local/bin/python -m src.ai_playlist.main >> /app/logs/cron.log 2>&1" | crontab -u m3u - && \
  chmod 644 /etc/crontab

# Metadata labels for best practices
ARG BUILD_DATE
ARG VCS_REF
ARG VERSION
ARG REPO_URL

LABEL maintainer="troy@troykelly.com" \
  org.opencontainers.image.title="AI Playlist Generator for AzuraCast" \
  org.opencontainers.image.description="AI-powered playlist generation using GPT-4 with automatic upload and scheduling to AzuraCast" \
  org.opencontainers.image.authors="Troy Kelly <troy@troykelly.com>" \
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

# Switch to root temporarily to start cron, then switch to non-root user
USER root

# Create entrypoint script
RUN echo '#!/bin/bash\n\
set -e\n\
\n\
# Start cron service\n\
service cron start\n\
\n\
# Print cron configuration\n\
echo "Cron schedule configured: Saturday at 1am (local time)"\n\
echo "Container timezone: $(cat /etc/timezone)"\n\
crontab -u m3u -l\n\
\n\
# Run initial playlist generation if RUN_ON_START is set\n\
if [ "${RUN_ON_START}" = "true" ]; then\n\
  echo "Running initial playlist generation..."\n\
  su - m3u -c "cd /app && python -m src.ai_playlist.main"\n\
fi\n\
\n\
# Keep container running and tail logs\n\
echo "Container started. Monitoring logs..."\n\
touch /app/logs/cron.log\n\
chown m3u:m3u /app/logs/cron.log\n\
tail -f /app/logs/cron.log\n\
' > /entrypoint.sh && chmod +x /entrypoint.sh

CMD ["/entrypoint.sh"]
