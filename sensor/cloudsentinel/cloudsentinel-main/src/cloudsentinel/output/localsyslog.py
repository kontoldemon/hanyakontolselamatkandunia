# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause


from __future__ import annotations

import syslog

import twisted.python.syslog

import cloudsentinel.core.cef
import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    localsyslog output
    """

    def start(self):
        self.format = CloudSentinelConfig.get("output_localsyslog", "format")
        facilityString = CloudSentinelConfig.get("output_localsyslog", "facility")
        self.facility = vars(syslog)["LOG_" + facilityString]
        self.syslog = twisted.python.syslog.SyslogObserver(
            prefix="cloudsentinel", facility=self.facility
        )

    def stop(self):
        pass

    def write(self, event):
        if "isError" not in event:
            event["isError"] = False

        if "system" not in event:
            event["system"] = "cloudsentinel"

        if self.format == "cef":
            self.syslog.emit(
                {
                    "message": [cloudsentinel.core.cef.formatCef(event)],
                    "isError": False,
                    "system": "cloudsentinel",
                }
            )
        else:
            # message appears with additional spaces if message key is defined
            event["message"] = [event["message"]]
            self.syslog.emit(event)
