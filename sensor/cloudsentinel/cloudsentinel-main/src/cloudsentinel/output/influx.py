# SPDX-FileCopyrightText: 2018 oliveriandrea <oliveriandrea@gmail.com>
# SPDX-FileCopyrightText: 2018-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import re

from influxdb import InfluxDBClient
from influxdb.exceptions import InfluxDBClientError
from twisted.python import log

import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    influx output
    """

    def start(self):
        host = CloudSentinelConfig.get("output_influx", "host", fallback="")
        port = CloudSentinelConfig.getint("output_influx", "port", fallback=8086)
        ssl = CloudSentinelConfig.getboolean("output_influx", "ssl", fallback=False)

        self.client = None
        try:
            self.client = InfluxDBClient(host=host, port=port, ssl=ssl, verify_ssl=ssl)
        except InfluxDBClientError as e:
            log.msg(f"output_influx: I/O error({e.code}): '{e.message}'")
            return

        if self.client is None:
            log.msg("output_influx: cannot instantiate client!")
            return

        if CloudSentinelConfig.has_option(
            "output_influx", "username"
        ) and CloudSentinelConfig.has_option("output_influx", "password"):
            username = CloudSentinelConfig.get("output_influx", "username")
            password = CloudSentinelConfig.get("output_influx", "password", raw=True)
            self.client.switch_user(username, password)

        try:
            dbname = CloudSentinelConfig.get("output_influx", "database_name")
        except Exception:
            dbname = "cloudsentinel"

        retention_policy_duration_default = "12w"
        retention_policy_name = dbname + "_retention_policy"

        if CloudSentinelConfig.has_option("output_influx", "retention_policy_duration"):
            retention_policy_duration = CloudSentinelConfig.get(
                "output_influx", "retention_policy_duration"
            )

            match = re.search(r"^\d+[dhmw]{1}$", retention_policy_duration)
            if not match:
                log.msg(
                    "output_influx: invalid retention policy."
                    f"Using default '{retention_policy_duration}'.."
                )
                retention_policy_duration = retention_policy_duration_default
        else:
            retention_policy_duration = retention_policy_duration_default

        database_list = self.client.get_list_database()
        dblist = [str(elem["name"]) for elem in database_list]

        if dbname not in dblist:
            self.client.create_database(dbname)
            self.client.create_retention_policy(
                retention_policy_name,
                retention_policy_duration,
                1,
                database=dbname,
                default=True,
            )
        else:
            retention_policies_list = self.client.get_list_retention_policies(
                database=dbname
            )
            rplist = [str(elem["name"]) for elem in retention_policies_list]
            if retention_policy_name not in rplist:
                self.client.create_retention_policy(
                    retention_policy_name,
                    retention_policy_duration,
                    1,
                    database=dbname,
                    default=True,
                )
            else:
                self.client.alter_retention_policy(
                    retention_policy_name,
                    database=dbname,
                    duration=retention_policy_duration,
                    replication=1,
                    default=True,
                )

        self.client.switch_database(dbname)

    def stop(self):
        pass

    def write(self, event):
        if self.client is None:
            log.msg("output_influx: client object is not instantiated")
            return

        # event id
        eventid = event["eventid"]

        # measurement init
        m = {
            "measurement": eventid.replace(".", "_"),
            "tags": {"session": event["session"], "src_ip": event["src_ip"]},
            "fields": {"sensor": self.sensor},
        }

        # event parsing
        if eventid in ["cloudsentinel.command.failed", "cloudsentinel.command.input"]:
            m["fields"].update(
                {
                    "input": event["input"],
                }
            )

        elif eventid == "cloudsentinel.session.connect":
            m["fields"].update(
                {
                    "protocol": event["protocol"],
                    "src_port": event["src_port"],
                    "dst_port": event["dst_port"],
                    "dst_ip": event["dst_ip"],
                }
            )

        elif eventid in ["cloudsentinel.login.success", "cloudsentinel.login.failed"]:
            m["fields"].update(
                {
                    "username": event["username"],
                    "password": event["password"],
                }
            )

        elif eventid == "cloudsentinel.session.file_download":
            m["fields"].update(
                {
                    "shasum": event.get("shasum"),
                    "url": event.get("url"),
                    "outfile": event.get("outfile"),
                }
            )

        elif eventid == "cloudsentinel.session.file_download.failed":
            m["fields"].update({"url": event.get("url")})

        elif eventid == "cloudsentinel.session.file_upload":
            m["fields"].update(
                {
                    "shasum": event.get("shasum"),
                    "outfile": event.get("outfile"),
                }
            )

        elif eventid == "cloudsentinel.session.closed":
            m["fields"].update({"duration": event["duration"]})

        elif eventid == "cloudsentinel.client.version":
            m["fields"].update(
                {
                    "version": ",".join(event["version"]),
                }
            )

        elif eventid == "cloudsentinel.client.kex":
            m["fields"].update(
                {
                    "maccs": ",".join(event["macCS"]),
                    "kexalgs": ",".join(event["kexAlgs"]),
                    "keyalgs": ",".join(event["keyAlgs"]),
                    "compcs": ",".join(event["compCS"]),
                    "enccs": ",".join(event["encCS"]),
                }
            )

        elif eventid == "cloudsentinel.client.size":
            m["fields"].update(
                {
                    "height": event["height"],
                    "width": event["width"],
                }
            )

        elif eventid == "cloudsentinel.client.var":
            m["fields"].update(
                {
                    "name": event["name"],
                    "value": event["value"],
                }
            )

        elif eventid == "cloudsentinel.client.fingerprint":
            m["fields"].update({"fingerprint": event["fingerprint"]})

            # cloudsentinel.direct-tcpip.data, cloudsentinel.direct-tcpip.request
            # cloudsentinel.log.closed
            # are not implemented
        else:
            # other events should be handled
            log.msg(f"output_influx: event '{eventid}' not handled. Skipping..")
            return

        result = self.client.write_points([m])

        if not result:
            log.msg(
                f"output_influx: error when writing '{eventid}' measurement in the db."
            )
