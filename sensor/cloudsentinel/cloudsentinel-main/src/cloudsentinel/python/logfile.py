# SPDX-FileCopyrightText: 2018-2025 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause


from __future__ import annotations

from os import environ
from pathlib import Path

from twisted.logger import textFileLogObserver
from twisted.python import logfile

from cloudsentinel.core.config import CloudSentinelConfig


class CloudSentinelDailyLogFile(logfile.DailyLogFile):
    """
    Overload original Twisted with improved date formatting
    """

    def suffix(self, tupledate: float | tuple[int, int, int]) -> str:
        """
        Return the suffix given a (year, month, day) tuple or unixtime
        """
        if isinstance(tupledate, tuple):
            return f"{tupledate[0]:02d}-{tupledate[1]:02d}-{tupledate[2]:02d}"
        if isinstance(tupledate, float):
            return "_".join(map(str, self.toDate(tupledate)))
        raise TypeError


def logger():
    """
    Custom logger that can log in a defined timezone and with custom
    roll over properties
    """
    directory = CloudSentinelConfig.get("honeypot", "log_path", fallback=".")

    logtype = CloudSentinelConfig.get("honeypot", "logtype", fallback="plain")
    if logtype == "rotating":
        cloudsentinellog = CloudSentinelDailyLogFile("cloudsentinel.log", directory)
    elif logtype == "plain":
        cloudsentinellog = open(Path(directory, "cloudsentinel.log"), "a", encoding="utf-8")
    else:
        raise ValueError

    # use Z for UTC (Zulu) time, it's shorter.
    if "TZ" in environ and environ["TZ"] == "UTC":
        timeFormat = "%Y-%m-%dT%H:%M:%S.%fZ"
    else:
        timeFormat = "%Y-%m-%dT%H:%M:%S.%f%z"

    return textFileLogObserver(cloudsentinellog, timeFormat=timeFormat)
