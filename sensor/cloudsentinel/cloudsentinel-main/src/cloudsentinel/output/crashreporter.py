# SPDX-FileCopyrightText: 2019-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

"""
CloudSentinel Crashreport

This output plugin is not like the others.
It has its own emit() function and does not use cloudsentinel eventid's
to avoid circular calls
"""

from __future__ import annotations

import json

import treq
from twisted.internet import defer
from twisted.logger._levels import LogLevel
from twisted.python import log

import cloudsentinel.core.output
from cloudsentinel._version import __version__
from cloudsentinel.core.config import CloudSentinelConfig

CLOUDSENTINEL_USER_AGENT = f"CloudSentinel Honeypot {__version__}".encode("ascii")
CLOUDSENTINEL_URL = "https://api.cloudsentinel.org/v1/crash"


class Output(cloudsentinel.core.output.Output):
    """
    CloudSentinel Crashreporter output
    """

    def start(self):
        """
        Start output plugin
        """
        self.apiKey = CloudSentinelConfig.get("output_cloudsentinel", "api_key", fallback=None)
        self.debug = CloudSentinelConfig.getboolean("output_cloudsentinel", "debug", fallback=False)

    def emit(self, event):
        """
        Note we override emit() here, unlike other plugins.
        """
        if event.get("log_level") == LogLevel.critical:
            self.crashreport(event)

    def stop(self):
        """
        Stop output plugin
        """
        pass

    def write(self, event):
        """
        events are done in emit() not in write()
        """
        pass

    @defer.inlineCallbacks
    def crashreport(self, entry):
        """
        Crash report
        """
        try:
            r = yield treq.post(
                CLOUDSENTINEL_URL,
                json.dumps(
                    {"log_text": entry.get("log_text"), "system": entry.get("system")}
                ).encode("ascii"),
                headers={
                    b"Content-Type": [b"application/json"],
                    b"User-Agent": [CLOUDSENTINEL_USER_AGENT],
                },
            )
            content = yield r.text()
            if self.debug:
                log.msg("crashreport: " + content)
        except Exception as e:
            log.msg("crashreporter failed" + repr(e))
