FROM python:3.12-slim

# Create a group and user with specific uid and gid
RUN groupadd -g 1000 m3u && useradd -u 1000 -g m3u -d /app -s /bin/bash m3u

WORKDIR /app

# Install dependencies and create a virtual environment
COPY requirements.txt .
RUN apt-get update && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y ffmpeg && \
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
