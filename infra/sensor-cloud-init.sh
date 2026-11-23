#!/usr/bin/env bash
set -euxo pipefail

DISK=/dev/disk/azure/scsi1/lun0
if [ -b "${DISK}" ]; then
    if ! blkid "${DISK}" >/dev/null 2>&1; then
        mkfs.ext4 -F "${DISK}"
    fi
    mkdir -p /opt/cloudsentinel
    mount "${DISK}" /opt/cloudsentinel
    grep -q "${DISK} /opt/cloudsentinel" /etc/fstab \
        || echo "${DISK} /opt/cloudsentinel ext4 defaults,nofail 0 2" >> /etc/fstab
fi
