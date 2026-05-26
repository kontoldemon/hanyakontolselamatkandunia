FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV CLOUDSENTINEL_VERSION=2.0.0

WORKDIR /app

# System deps for cryptography + nftables + iptables
RUN apt-get update -qq && apt-get install -y -qq --no-install-recommends \
    iptables nftables netbase ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

# Install gVisor (runsc) for sandbox isolation
RUN ARCH=$(dpkg --print-architecture) && \
    case "${ARCH}" in \
        amd64) GVISOR_ARCH="x86_64" ;; \
        arm64) GVISOR_ARCH="aarch64" ;; \
        *) echo "Unsupported gVisor arch: ${ARCH}"; exit 1 ;; \
    esac && \
    URL="https://storage.googleapis.com/gvisor/releases/release/latest/${GVISOR_ARCH}" && \
    curl -fsSLO "${URL}/runsc" && \
    curl -fsSLO "${URL}/runsc.sha512" && \
    sha512sum -c runsc.sha512 && \
    install -m 0755 runsc /usr/local/bin/runsc && \
    rm -f runsc runsc.sha512

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
