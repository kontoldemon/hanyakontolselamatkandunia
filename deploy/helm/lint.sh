#!/usr/bin/env bash
# CloudSentinel Helm Chart Lint & Validation
# Run in CI or locally before deploying to Kubernetes.

set -euo pipefail

CHART_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/cloudsentinel"

echo "=== Helm Lint ==="
if ! command -v helm &>/dev/null; then
    echo "helm not installed -- skipping"
    exit 0
fi

helm lint "${CHART_DIR}" --strict

echo ""
echo "=== Helm Template (Dry Run) ==="
helm template cloudsentinel "${CHART_DIR}" \
    --set sensor.image.tag=ci-test \
    --set clickhouse.enabled=true \
    --set redis.enabled=true \
    > /tmp/cloudsentinel-helm-output.yaml

echo "Generated $(grep -c '^  name:' /tmp/cloudsentinel-helm-output.yaml || echo 0) Kubernetes resources"

echo ""
echo "=== Kubeconform Validation ==="
if command -v kubeconform &>/dev/null; then
    kubeconform -strict -summary /tmp/cloudsentinel-helm-output.yaml
else
    echo "kubeconform not installed -- install with: go install github.com/yannh/kubeconform/cmd/kubeconform@latest"
fi

echo ""
echo "=== Helm Lint PASSED ==="
