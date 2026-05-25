# SPDX-FileCopyrightText: 2009 Upi Tamminen <desaster@gmail.com>
# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

import sys

from twisted.python import log

try:
    import cloudsentinel._version as cloudsentinel_version

    __version__ = cloudsentinel_version
except ModuleNotFoundError:
    log.err(
        "CloudSentinel is not installed. Run `pip install -e .` to install CloudSentinel into your virtual enviroment"
    )
    sys.exit(1)
