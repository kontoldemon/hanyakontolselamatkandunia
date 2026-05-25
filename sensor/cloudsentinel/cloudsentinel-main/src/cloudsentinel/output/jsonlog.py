# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import json
import os
from pathlib import Path

from twisted.python import log

import cloudsentinel.core.output
import cloudsentinel.python.logfile
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    jsonlog output
    """

    def start(self):
        self.epoch_timestamp = CloudSentinelConfig.getboolean(
            "output_jsonlog", "epoch_timestamp", fallback=False
        )
        fn = CloudSentinelConfig.get("output_jsonlog", "logfile", fallback="cloudsentinel.json")
        dirs = os.path.dirname(fn)
        base = os.path.basename(fn)

        logtype = CloudSentinelConfig.get("honeypot", "logtype", fallback="plain")
        if logtype == "rotating":
            self.outfile = cloudsentinel.python.logfile.CloudSentinelDailyLogFile(
                base, dirs, defaultMode=0o664
            )
        elif logtype == "plain":
            self.outfile = open(Path(dirs, base), "w", encoding="utf-8")
        else:
            raise ValueError

    def stop(self):
        if self.outfile:
            self.outfile.flush()

    def write(self, event):
        if self.epoch_timestamp:
            event["epoch"] = int(event["time"] * 1000000 / 1000)
        for i in list(event):
            # Remove twisted 15 legacy keys
            if i.startswith("log_") or i == "time" or i == "system":
                del event[i]
        try:
            json.dump(event, self.outfile, separators=(",", ":"))
            self.outfile.write("\n")
            self.outfile.flush()
        except TypeError:
            log.err("jsonlog: Can't serialize: '" + repr(event) + "'")
