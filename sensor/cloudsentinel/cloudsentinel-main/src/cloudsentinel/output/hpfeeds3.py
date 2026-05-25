# SPDX-FileCopyrightText: 2018 Jc2k <john.carr@unrouted.co.uk>
# SPDX-FileCopyrightText: 2018-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

"""
Output plugin for HPFeeds
"""

from __future__ import annotations

import json
import logging

from hpfeeds.twisted import ClientSessionService
from twisted.internet import endpoints, reactor, ssl
from twisted.python import log

import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    Output plugin for HPFeeds
    """

    channel = "cloudsentinel.sessions"

    def start(self):
        if CloudSentinelConfig.has_option("output_hpfeeds3", "channel"):
            self.channel = CloudSentinelConfig.get("output_hpfeeds3", "channel")

        if CloudSentinelConfig.has_option("output_hpfeeds3", "endpoint"):
            endpoint = CloudSentinelConfig.get("output_hpfeeds3", "endpoint")
        else:
            server = CloudSentinelConfig.get("output_hpfeeds3", "server")
            port = CloudSentinelConfig.getint("output_hpfeeds3", "port")

            if CloudSentinelConfig.has_option("output_hpfeeds3", "tlscert"):
                with open(CloudSentinelConfig.get("output_hpfeeds3", "tlscert")) as fp:
                    authority = ssl.Certificate.loadPEM(fp.read())
                options = ssl.optionsForClientTLS(server, authority)
                endpoint = endpoints.SSL4ClientEndpoint(reactor, server, port, options)
            else:
                endpoint = endpoints.HostnameEndpoint(reactor, server, port)

        ident = CloudSentinelConfig.get("output_hpfeeds3", "identifier")
        secret = CloudSentinelConfig.get("output_hpfeeds3", "secret")

        self.meta = {}

        self.client = ClientSessionService(endpoint, ident, secret)
        self.client.startService()

    def stop(self):
        self.client.stopService()

    def write(self, event):
        session = event["session"]
        if event["eventid"] == "cloudsentinel.session.connect":
            self.meta[session] = {
                "session": session,
                "startTime": event["timestamp"],
                "endTime": "",
                "peerIP": event["src_ip"],
                "peerPort": event["src_port"],
                "hostIP": event["dst_ip"],
                "hostPort": event["dst_port"],
                "loggedin": None,
                "credentials": [],
                "commands": [],
                "unknownCommands": [],
                "urls": [],
                "version": None,
                "ttylog": None,
                "hashes": set(),
                "protocol": event["protocol"],
            }

        elif event["eventid"] == "cloudsentinel.login.success":
            u, p = event["username"], event["password"]
            self.meta[session]["loggedin"] = (u, p)

        elif event["eventid"] == "cloudsentinel.login.failed":
            u, p = event["username"], event["password"]
            self.meta[session]["credentials"].append((u, p))

        elif event["eventid"] == "cloudsentinel.command.input":
            c = event["input"]
            self.meta[session]["commands"].append(c)

        elif event["eventid"] == "cloudsentinel.command.failed":
            uc = event["input"]
            self.meta[session]["unknownCommands"].append(uc)

        elif event["eventid"] == "cloudsentinel.session.file_download":
            if "url" in event:
                url = event["url"]
                self.meta[session]["urls"].append(url)
            self.meta[session]["hashes"].add(event["shasum"])

        elif event["eventid"] == "cloudsentinel.session.file_upload":
            self.meta[session]["hashes"].add(event["shasum"])

        elif event["eventid"] == "cloudsentinel.client.version":
            v = event["version"]
            self.meta[session]["version"] = v

        elif event["eventid"] == "cloudsentinel.log.closed":
            # event["ttylog"]
            with open(event["ttylog"], "rb") as ttylog:
                self.meta[session]["ttylog"] = ttylog.read().hex()

        elif event["eventid"] == "cloudsentinel.session.closed":
            meta = self.meta.pop(session, None)
            if meta:
                log.msg("publishing metadata to hpfeeds", logLevel=logging.DEBUG)
                meta["endTime"] = event["timestamp"]
                meta["hashes"] = list(meta["hashes"])
                self.client.publish(self.channel, json.dumps(meta).encode("utf-8"))
