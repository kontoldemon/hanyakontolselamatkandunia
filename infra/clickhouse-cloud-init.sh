#!/usr/bin/env bash
set -euxo pipefail

export DEBIAN_FRONTEND=noninteractive

apt-get update -qq
apt-get install -y -qq apt-transport-https ca-certificates curl gnupg

install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://packages.clickhouse.com/rpm/lts/repodata/repomd.xml.key \
    | gpg --dearmor -o /etc/apt/keyrings/clickhouse.gpg
echo "deb [signed-by=/etc/apt/keyrings/clickhouse.gpg] https://packages.clickhouse.com/deb stable main" \
    > /etc/apt/sources.list.d/clickhouse.list
apt-get update -qq
apt-get install -y -qq clickhouse-server clickhouse-client

systemctl stop clickhouse-server || true

DISK=/dev/disk/azure/scsi1/lun0
if [ -b "${DISK}" ]; then
    if ! blkid "${DISK}" >/dev/null 2>&1; then
        mkfs.ext4 -F "${DISK}"
    fi
    mkdir -p /var/lib/clickhouse
    mount "${DISK}" /var/lib/clickhouse
    grep -q "${DISK} /var/lib/clickhouse" /etc/fstab \
        || echo "${DISK} /var/lib/clickhouse ext4 defaults,nofail 0 2" >> /etc/fstab
    chown clickhouse:clickhouse /var/lib/clickhouse
fi

cat > /etc/clickhouse-server/config.d/cloudsentinel-network.xml <<'XML'
<clickhouse>
    <listen_host>0.0.0.0</listen_host>
</clickhouse>
XML

systemctl enable clickhouse-server
systemctl restart clickhouse-server
