FROM python:3.12-slim

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

# Create a group and user with a specific uid and gid
RUN groupadd -g 1000 m3u && useradd -u 1000 -g m3u -d /app -s /bin/bash m3u

WORKDIR /app

# Install dependencies and create a virtual environment
COPY requirements.txt .
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg wkhtmltopdf && \
    pip install --no-cache-dir -r requirements.txt && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Copy application code and default configuration with proper ownership
COPY --chown=m3u:m3u src /app/src

# Ensure the working directory has correct ownership
RUN chown -R m3u:m3u /app

# Switch to non-root user
USER m3u

CMD ["python", "src/main.py"]
