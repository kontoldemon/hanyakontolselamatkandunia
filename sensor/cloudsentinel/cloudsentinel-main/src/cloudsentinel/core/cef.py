# SPDX-FileCopyrightText: 2016-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause


#  cloudsentinel.client.fingerprint
#  cloudsentinel.client.size
#  cloudsentinel.client.var
#  cloudsentinel.client.version
#  cloudsentinel.command.failed
#  cloudsentinel.command.success
#  cloudsentinel.direct-tcpip.data
#  cloudsentinel.direct-tcpip.request
#  cloudsentinel.log.closed
#  cloudsentinel.login.failed
#  cloudsentinel.login.success
#  cloudsentinel.session.closed
#  cloudsentinel.session.connect
#  cloudsentinel.session.file_download
#  cloudsentinel.session.file_upload

from __future__ import annotations


def formatCef(logentry: dict[str, str]) -> str:
    """
    Take logentry and turn into CEF string
    """
    # Jan 18 11:07:53 host CEF:Version|Device Vendor|Device Product|
    # Device Version|Signature ID|Name|Severity|[Extension]
    cefVendor = "CloudSentinel"
    cefProduct = "CloudSentinel"
    cefVersion = "1.0"
    cefSignature = logentry["eventid"]
    cefName = logentry["eventid"]
    cefSeverity = "5"

    cefExtensions = {
        "app": "SSHv2",
        "destinationServicename": "sshd",
        "deviceExternalId": logentry["sensor"],
        "msg": logentry["message"],
        "src": logentry["src_ip"],
        "proto": "tcp",
    }

    match logentry["eventid"]:
        case "cloudsentinel.session.connect":
            cefExtensions["spt"] = logentry["src_port"]
            cefExtensions["dpt"] = logentry["dst_port"]
            cefExtensions["src"] = logentry["src_ip"]
            cefExtensions["dst"] = logentry["dst_ip"]
        case "cloudsentinel.login.success":
            cefExtensions["duser"] = logentry["username"]
            cefExtensions["outcome"] = "success"
        case "cloudsentinel.login.failed":
            cefExtensions["duser"] = logentry["username"]
            cefExtensions["outcome"] = "failed"
        case "cloudsentinel.file.file_download" | "cloudsentinel.file.file_upload":
            cefExtensions["filehash"] = logentry["filehash"]
            cefExtensions["filePath"] = logentry["filename"]
            cefExtensions["fsize"] = logentry["size"]

    # 'out' 'outcome'  request, rt

    cefList = []
    for key in cefExtensions:
        value = str(cefExtensions[key])
        cefList.append(f"{key}={value}")

    cefExtension = " ".join(cefList)

    cefString = (
        "CEF:0|"
        + cefVendor
        + "|"
        + cefProduct
        + "|"
        + cefVersion
        + "|"
        + cefSignature
        + "|"
        + cefName
        + "|"
        + cefSeverity
        + "|"
        + cefExtension
    )

    return cefString
