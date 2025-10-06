FROM mcr.microsoft.com/devcontainers/python:1-3.13-bookworm

# Set non-interactive frontend for apt
ENV DEBIAN_FRONTEND=noninteractive

# Update package repositories and upgrade existing packages
RUN apt-get update && apt-get upgrade -y

# Install system packages for development and networking tools
RUN apt-get install -y \
    ripgrep \
    curl \
    dnsutils \
    iputils-ping \
    net-tools \
    traceroute \
    tcpdump \
    iproute2 \
    telnet \
    nmap \
    iperf3 \
    mtr-tiny \
    wget \
    gnupg2 \
    software-properties-common \
    apt-transport-https \
    ca-certificates \
    lsb-release \
    zsh \
    git \
    vim \
    && rm -rf /var/lib/apt/lists/*

# Get architecture for multi-platform support
RUN ARCH=$(dpkg --print-architecture) && echo "Architecture: $ARCH"

# Install Node.js current version (not LTS)
RUN curl -fsSL https://deb.nodesource.com/setup_current.x | bash - \
    && apt-get install -y nodejs

# Verify Node.js installation and get npm version
RUN node --version && npm --version

# Install pnpm globally (latest version)
RUN npm install -g pnpm@latest

# Install TypeScript globally (latest version)
RUN npm install -g typescript@latest

# Install Claude Code CLI (required for claude-flow swarm functionality)
RUN curl -fsSL https://claude.ai/install.sh | bash -s latest && \
    # Verify installation
    /root/.local/bin/claude --version

# Verify installations
RUN pnpm --version && tsc --version

# Install GitHub CLI
RUN curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg \
    && sudo chmod go+r /usr/share/keyrings/githubcli-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null \
    && sudo apt-get update \
    && sudo apt-get install -y gh \
    && sudo rm -rf /var/lib/apt/lists/*

# Install uv package manager for Python and install packages
RUN curl -LsSf https://astral.sh/uv/install.sh | sh && \
    /root/.local/bin/uv pip install --system \
    aiofiles \
    aiohttp \
    aioredis \
    apscheduler \
    asyncio \
    beautifulsoup4 \
    cachetools \
    celery \
    click>=8.0.0 \
    dramatiq \
    fastapi \
    gitpython>=3.1.0 \
    httpx \
    jinja2 \
    jsonrpc \
    langdetect \
    loguru \
    lxml \
    markdown2 \
    pydantic>=2.0.0 \
    pydantic-settings>=2.0.0 \
    python-dateutil \
    python-telegram-bot \
    pytz \
    pyyaml>=6.0.0 \
    redis \
    rich>=13.0.0 \
    structlog \
    tenacity \
    typer \
    uvicorn \
    watchdog>=3.0.0 \
    websockets

# Set uv in PATH for all users
ENV PATH="/root/.local/bin:$PATH"

# Make uv and uvx available to all users by copying to /usr/local/bin
RUN cp /root/.local/bin/uv /usr/local/bin/uv && \
    cp /root/.local/bin/uvx /usr/local/bin/uvx && \
    chmod 755 /usr/local/bin/uv /usr/local/bin/uvx && \
    chown root:root /usr/local/bin/uv /usr/local/bin/uvx

# Configure zsh as default shell for vscode user
RUN usermod -s $(which zsh) vscode

# Create .zshrc for vscode user with basic configuration
USER vscode
WORKDIR /home/vscode

RUN uv tool install specify-cli --from git+https://github.com/github/spec-kit.git

RUN echo '# Aperim Template Development Environment' > ~/.zshrc \
    && echo 'export PATH="$HOME/.cargo/bin:$PATH"' >> ~/.zshrc \
    && echo 'export PYTHONPATH="/workspaces:$PYTHONPATH"' >> ~/.zshrc \
    && echo 'export NODE_ENV=development' >> ~/.zshrc \
    && echo '' >> ~/.zshrc \
    && echo '# Aliases' >> ~/.zshrc \
    && echo 'alias ll="ls -la"' >> ~/.zshrc \
    && echo 'alias la="ls -A"' >> ~/.zshrc \
    && echo 'alias l="ls -CF"' >> ~/.zshrc \
    && echo 'alias ..="cd .."' >> ~/.zshrc \
    && echo 'alias ...="cd ../.."' >> ~/.zshrc \
    && echo '' >> ~/.zshrc \
    && echo '# Development shortcuts' >> ~/.zshrc \
    && echo 'alias workspace="cd /workspaces"' >> ~/.zshrc \
    && echo 'alias agent="cd /workspaces/.agent"' >> ~/.zshrc

# Reset to root for any remaining setup
USER root

# Set working directory to workspaces
WORKDIR /workspaces

# Reset to non-interactive mode
ENV DEBIAN_FRONTEND=

# Final verification of all tools
RUN echo "=== Installation Verification ===" \
    && python3 --version \
    && node --version \
    && npm --version \
    && pnpm --version \
    && tsc --version \
    && uv --version \
    && zsh --version \
    && echo "=== All tools installed successfully ==="