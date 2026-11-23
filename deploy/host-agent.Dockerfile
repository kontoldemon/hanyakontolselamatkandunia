FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update -qq && \
    apt-get install -y -qq --no-install-recommends iptables && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "redis>=5.0.1,<6.0"

COPY src/host_agent/iptables_worker.py /app/iptables_worker.py

WORKDIR /app
CMD ["python", "/app/iptables_worker.py"]
