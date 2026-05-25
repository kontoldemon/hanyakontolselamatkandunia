# SPDX-FileCopyrightText: 2015-2024 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause


from __future__ import annotations

import cloudsentinel.core.cef
import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    textlog output
    """

    def start(self):
        self.format = CloudSentinelConfig.get("output_textlog", "format")
        self.outfile = open(
            CloudSentinelConfig.get("output_textlog", "logfile"), "a", encoding="utf-8"
        )

    def stop(self):
        pass

    def write(self, event):
        if self.format == "cef":
            self.outfile.write("{} ".format(event["timestamp"]))
            self.outfile.write(f"{cloudsentinel.core.cef.formatCef(event)}\n")
        else:
            self.outfile.write("{} ".format(event["timestamp"]))
            self.outfile.write("{} ".format(event["session"]))
            self.outfile.write("{}\n".format(event["message"]))
        self.outfile.flush()
