FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive
ENV DISPLAY=:99
ENV ZONES_HOME=/zones
ENV ZONES_RELEASE_URL=https://github.com/nguemechieu/ZONES/archive/refs/tags/v1.zip
ENV WINEPREFIX=/root/.wine
ENV WINEDEBUG=-all

WORKDIR /zones

# Enable 32-bit support for Wine / MT4
RUN dpkg --add-architecture i386 && apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    unzip \
    git \
    ca-certificates \
    python3-tk \
    python3-dev \
    build-essential \
    xvfb \
    fluxbox \
    x11vnc \
    novnc \
    websockify \
    chromium \
    wine \
    wine32 \
    wine64 \
    winbind \
    && rm -rf /var/lib/apt/lists/*

# Download and install ZONES release
RUN mkdir -p /tmp/zones_release && \
    wget -O /tmp/zones.zip "$ZONES_RELEASE_URL" && \
    unzip /tmp/zones.zip -d /tmp/zones_release && \
    cp -r /tmp/zones_release/*/* /zones/ && \
    rm -rf /tmp/zones.zip /tmp/zones_release

# Install Python dependencies if requirements.txt exists
RUN python -m pip install --upgrade pip setuptools wheel && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

# Optional: copy local MQL4 folder into the image.
# Put your MQL4 folder beside this Dockerfile before building.
COPY MQL4 /zones/MQL4

# Copy startup script
COPY docker-start.sh /usr/local/bin/docker-start.sh
RUN chmod +x /usr/local/bin/docker-start.sh

# ZONES dashboard
EXPOSE 8787

# ZONES WebSocket bridge
EXPOSE 8090

# Prometheus metrics
EXPOSE 9108

# noVNC browser desktop
EXPOSE 6080

CMD ["/usr/local/bin/docker-start.sh"]