# SPDX-FileCopyrightText: 2017 Claud Xiao
# SPDX-FileCopyrightText: 2017-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

import pymongo
from twisted.python import log

import cloudsentinel.core.output
from cloudsentinel.core.config import CloudSentinelConfig


class Output(cloudsentinel.core.output.Output):
    """
    mongodb output
    """

    def insert_one(self, collection, event):
        try:
            object_id = collection.insert_one(event).inserted_id
        except Exception as e:
            log.msg(f"mongo error - {e}")
        else:
            return object_id

    def update_one(self, collection, session, doc):
        try:
            object_id = collection.update_one({"session": session}, {"$set": doc})
        except Exception as e:
            log.msg(f"mongo error - {e}")
        else:
            return object_id

    def start(self):
        db_addr = CloudSentinelConfig.get("output_mongodb", "connection_string")
        db_name = CloudSentinelConfig.get("output_mongodb", "database")

        try:
            self.mongo_client = pymongo.MongoClient(db_addr)
            self.mongo_db = self.mongo_client[db_name]
            # Define Collections.
            self.col_sensors = self.mongo_db["sensors"]
            self.col_sessions = self.mongo_db["sessions"]
            self.col_auth = self.mongo_db["auth"]
            self.col_input = self.mongo_db["input"]
            self.col_downloads = self.mongo_db["downloads"]
            self.col_clients = self.mongo_db["clients"]
            self.col_ttylog = self.mongo_db["ttylog"]
            self.col_keyfingerprints = self.mongo_db["keyfingerprints"]
            self.col_event = self.mongo_db["event"]
            self.col_ipforwards = self.mongo_db["ipforwards"]
            self.col_ipforwardsdata = self.mongo_db["ipforwardsdata"]
        except Exception as e:
            log.msg(f"output_mongodb: Error: {e!s}")

    def stop(self):
        self.mongo_client.close()

    def write(self, event):
        for i in list(event):
            # Remove twisted 15 legacy keys
            if i.startswith("log_"):
                del event[i]

        match event["eventid"]:
            case "cloudsentinel.session.connect":
                # Check if sensor exists, else add it.
                doc = self.col_sensors.find_one({"sensor": self.sensor})
                if not doc:
                    self.insert_one(self.col_sensors, event)

                # Prep extra elements just to make django happy later on
                event["starttime"] = event["timestamp"]
                event["endtime"] = None
                event["sshversion"] = None
                event["termsize"] = None
                log.msg("Session Created")
                self.insert_one(self.col_sessions, event)

            case "cloudsentinel.login.success" | "cloudsentinel.login.failed":
                self.insert_one(self.col_auth, event)

            case "cloudsentinel.command.input" | "cloudsentinel.command.failed":
                self.insert_one(self.col_input, event)

            case "cloudsentinel.session.file_download":
                self.insert_one(self.col_downloads, event)

            case "cloudsentinel.client.version":
                doc = self.col_sessions.find_one({"session": event["session"]})
                if doc:
                    doc["sshversion"] = event["version"]
                    self.update_one(self.col_sessions, event["session"], doc)

            case "cloudsentinel.client.size":
                doc = self.col_sessions.find_one({"session": event["session"]})
                if doc:
                    doc["termsize"] = f"{event['width']}x{event['height']}"
                    self.update_one(self.col_sessions, event["session"], doc)

            case "cloudsentinel.session.closed":
                doc = self.col_sessions.find_one({"session": event["session"]})
                if doc:
                    doc["endtime"] = event["timestamp"]
                    self.update_one(self.col_sessions, event["session"], doc)

            case "cloudsentinel.log.closed":
                # ToDo Compress to opimise the space and if your sending to remote db
                with open(event["ttylog"]) as ttylog:
                    event["ttylogpath"] = event["ttylog"]
                    event["ttylog"] = ttylog.read().encode().hex()
                self.insert_one(self.col_ttylog, event)

            case "cloudsentinel.client.fingerprint":
                self.insert_one(self.col_keyfingerprints, event)

            case "cloudsentinel.direct-tcpip.request":
                self.insert_one(self.col_ipforwards, event)

            case "cloudsentinel.direct-tcpip.data":
                self.insert_one(self.col_ipforwardsdata, event)

            # Catch any other event types
            case _:
                self.insert_one(self.col_event, event)
