# SPDX-FileCopyrightText: 2024 mjovanovic9999
# SPDX-FileCopyrightText: 2024-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Simple remote syslog plugin.
"""

import logging
import logging.handlers
import socket

import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    def start(self):
        self.host = CloudSentinelConfig.get(
            "output_remotesyslog", "host", fallback="127.0.0.1"
        )

        self.port = int(CloudSentinelConfig.get("output_remotesyslog", "port", fallback="514"))

        protocol = CloudSentinelConfig.get(
            "output_remotesyslog", "protocol", fallback="udp"
        ).lower()

        self.logger = logging.getLogger("cloudsentinelLogger")

        self.handler = logging.handlers.SysLogHandler(
            address=(self.host, self.port),
            socktype=None if protocol == "udp" else socket.SOCK_STREAM,
        )

        self.logger.addHandler(self.handler)

    def stop(self):
        self.handler.flush()
        self.logger.removeHandler(self.handler)
        self.handler.close()

    def write(self, event):
        for i in list(event):
            # Remove twisted 15 legacy keys
            if i.startswith("log_") or i == "time" or i == "system":
                del event[i]

        self.logger.warning(repr(event) + "\n")
