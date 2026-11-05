FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CLOUDSENTINEL_VERSION=2.0.0

WORKDIR /app

# System deps for cryptography + nftables + iptables + gVisor
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    iptables nftables netbase ca-certificates curl gnupg && \
    rm -rf /var/lib/apt/lists/*

# Install gVisor (runsc) from the official apt repository
RUN curl -fsSL https://gvisor.dev/archive.key | gpg --batch --yes --dearmor -o /usr/share/keyrings/gvisor-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/gvisor-archive-keyring.gpg] https://storage.googleapis.com/gvisor/releases release main" > /etc/apt/sources.list.d/gvisor.list && \
    apt-get update -qq && apt-get install -y -qq --no-install-recommends runsc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY . /app/cloudsentinel/

# Create runtime directories
RUN mkdir -p /app/var/lib/cloudsentinel/{tls,tty,wal} /app/var/log/cloudsentinel && \
    chown -R 1000:1000 /app/var

USER 1000:1000

EXPOSE 2222
EXPOSE 8080
EXPOSE 8443
EXPOSE 53/udp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/healthz')" || exit 1

CMD ["python", "-m", "cloudsentinel.server", "--config", "/app/cloudsentinel/configs/usas-production.yaml", "--env", "/app/cloudsentinel/.env"]
