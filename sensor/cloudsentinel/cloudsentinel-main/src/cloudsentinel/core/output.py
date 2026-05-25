# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import abc
import re
import socket
import time
from os import environ
from re import Pattern
from typing import Any

from twisted.internet import reactor
from twisted.logger import formatTime

from cloudsentinel.core.config import CloudSentinelConfig

# Events:
#  cloudsentinel.client.fingerprint
#  cloudsentinel.client.size
#  cloudsentinel.client.var
#  cloudsentinel.client.version
#  cloudsentinel.command.input
#  cloudsentinel.command.failed
#  cloudsentinel.command.success (deprecated)
#  cloudsentinel.direct-tcpip.data
#  cloudsentinel.direct-tcpip.request
#  cloudsentinel.log.closed
#  cloudsentinel.login.failed
#  cloudsentinel.login.success
#  cloudsentinel.session.closed
#  cloudsentinel.session.connect
#  cloudsentinel.session.file_download
#  cloudsentinel.session.file_upload


# The time is available in two formats in each event, as key 'time'
# in epoch format and in key 'timestamp' as a ISO compliant string
# in UTC.


def convert(data):
    """
    This converts a nested dictionary with bytes in it to string
    """
    match data:
        case str():
            return data
        case dict():
            return {convert(key): convert(value) for key, value in data.items()}
        case list():
            return [convert(element) for element in data]
        case bytes():
            try:
                return data.decode("utf-8")
            except UnicodeDecodeError:
                return repr(data)
        case _:
            return data


class Output(metaclass=abc.ABCMeta):
    """
    This is the abstract base class intended to be inherited by
    cloudsentinel output plugins. Plugins require the mandatory
    methods: stop, start and write
    """

    def __init__(self) -> None:
        self.sessions: dict[str, str] = {}
        self.ips: dict[str, str] = {}
        self.session_metadata: dict[str, dict[str, str]] = {}

        # Need these for each individual transport, or else the session numbers overlap
        self.sshRegex: Pattern[str] = re.compile(".*SSHTransport,([0-9]+),[0-9a-f:.]+$")
        self.telnetRegex: Pattern[str] = re.compile(
            ".*TelnetTransport,([0-9]+),[0-9a-f:.]+$"
        )
        self.sensor: str = CloudSentinelConfig.get(
            "honeypot", "sensor_name", fallback=socket.gethostname()
        )
        self.uuid: str = CloudSentinelConfig.get("honeypot", "uuid", fallback="unknown")

        self.timeFormat: str
        # use Z for UTC (Zulu) time, it's shorter.
        if "TZ" in environ and environ["TZ"] == "UTC":
            self.timeFormat = "%Y-%m-%dT%H:%M:%S.%fZ"
        else:
            self.timeFormat = "%Y-%m-%dT%H:%M:%S.%f%z"

        # Event trigger so that stop() is called by the reactor when stopping
        reactor.addSystemEventTrigger("before", "shutdown", self.stop)

        self.start()

    def logDispatch(self, **kw: str) -> None:
        """
        Use logDispatch when the HoneypotTransport prefix is not available.
        Here you can explicitly set the sessionIds to tie the sessions together
        """
        ev = kw
        # ev["message"] = msg
        self.emit(ev)

    @abc.abstractmethod
    def start(self) -> None:
        """
        Abstract method to initialize output plugin
        """
        pass

    @abc.abstractmethod
    def stop(self) -> None:
        """
        Abstract method to shut down output plugin
        """
        pass

    @abc.abstractmethod
    def write(self, event: dict[str, Any]) -> None:
        """
        Handle a general event within the output plugin
        """
        pass

    def emit(self, event: dict) -> None:
        """
        This is the main emit() hook that gets called by the the Twisted logging

        To make this work with CloudSentinel, the event dictionary needs the following keys:
        - 'eventid'
        - 'sessionno' or 'session'
        - 'message' or 'format'
        """
        sessionno: str

        # Ignore stdout and stderr in output plugins
        if "printed" in event:
            return

        # Ignore anything without eventid
        if "eventid" not in event:
            return

        # Ignore anything without session information
        if (
            "sessionno" not in event
            and "session" not in event
            and "system" not in event
        ):
            return

        # Ignore anything without message
        if "message" not in event and "format" not in event:
            return

        ev: dict[str, any] = convert(event)  # type: ignore
        ev["sensor"] = self.sensor
        ev["uuid"] = self.uuid

        ev.pop("isError", None)

        # Add ISO timestamp and sensor data
        if "time" not in ev:
            ev["time"] = time.time()
        ev["timestamp"] = formatTime(ev["time"], timeFormat=self.timeFormat)

        if "format" in ev and ("message" not in ev or ev["message"] == ()):
            try:
                ev["message"] = ev["format"] % ev  # type: ignore
                del ev["format"]
            except Exception:
                pass

        # Explicit sessionno (from logDispatch) overrides from 'system'
        if "sessionno" in ev:
            sessionno = ev["sessionno"]
            del ev["sessionno"]
        # Maybe it's passed explicitly
        elif "session" in ev:
            # reverse engineer sessionno
            try:
                sessionno = next(
                    key
                    for key, value in self.sessions.items()
                    if value == ev["session"]
                )
            except StopIteration:
                return
        # Extract session id from the twisted log prefix
        elif "system" in ev:
            sessionno = "0"
            telnetmatch = self.telnetRegex.match(ev["system"])
            if telnetmatch:
                sessionno = f"T{telnetmatch.groups()[0]}"
            else:
                sshmatch = self.sshRegex.match(ev["system"])
                if sshmatch:
                    sessionno = f"S{sshmatch.groups()[0]}"
            if sessionno == "0":
                return
        else:
            print(f"Can't determine sessionno: {ev!r}")  # noqa: T201
            return

        if sessionno in self.ips:
            ev["src_ip"] = self.ips[sessionno]

        # Connection event is special. adds to session list
        if ev["eventid"] == "cloudsentinel.session.connect":
            self.sessions[sessionno] = ev["session"]
            self.ips[sessionno] = ev["src_ip"]
            self.session_metadata[ev["session"]] = {}
        else:
            ev["session"] = self.sessions[sessionno]

        metadata = self.session_metadata.setdefault(ev["session"], {})
        if ev["eventid"] == "cloudsentinel.client.kex":
            for key in ("hassh", "hasshAlgorithms"):
                if key in ev:
                    metadata[key] = ev[key]
        for key, value in metadata.items():
            ev.setdefault(key, value)

        if sessionno[0] == "S":
            ev["protocol"] = "ssh"
        elif sessionno[0] == "T":
            ev["protocol"] = "telnet"
        else:
            ev["protocol"] = "unknown"

        self.write(ev)

        # Disconnect is special, remove cached data
        if ev["eventid"] == "cloudsentinel.session.closed":
            self.session_metadata.pop(ev["session"], None)
            del self.sessions[sessionno]
            del self.ips[sessionno]
