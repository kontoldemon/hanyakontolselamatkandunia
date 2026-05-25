# SPDX-FileCopyrightText: 2020 Peter Sufliarsky
# SPDX-FileCopyrightText: 2018-2024 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause
from __future__ import annotations

import os
import unittest

from cloudsentinel.shell.protocol import HoneyPotInteractiveProtocol
from cloudsentinel.test.fake_server import FakeAvatar, FakeServer
from cloudsentinel.test.fake_transport import FakeTransport

os.environ["CLOUDSENTINEL_HONEYPOT_DATA_PATH"] = "data"
os.environ["CLOUDSENTINEL_HONEYPOT_DOWNLOAD_PATH"] = "/tmp"
os.environ["CLOUDSENTINEL_SHELL_FILESYSTEM"] = "src/cloudsentinel/data/fs.pickle"

TRY_CHMOD_HELP_MSG = b"Try 'base64 --help' for more information.\n"
PROMPT = b"root@unitTest:~# "


class ShellBase64CommandTests(unittest.TestCase):
    """Tests for cloudsentinel/commands/base64.py"""

    proto = HoneyPotInteractiveProtocol(FakeAvatar(FakeServer()))
    tr = FakeTransport("", "31337")

    @classmethod
    def setUpClass(cls) -> None:
        cls.proto.makeConnection(cls.tr)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.proto.connectionLost()

    def setUp(self) -> None:
        self.tr.clear()

    def test_base64_command_001(self) -> None:
        self.proto.lineReceived(b"echo cloudsentinel | base64")
        self.assertEqual(self.tr.value(), b"Y293cmllCg==\n" + PROMPT)

    def test_base64_command_002(self) -> None:
        self.proto.lineReceived(b"echo Y293cmllCg== | base64 -d")
        self.assertEqual(self.tr.value(), b"cloudsentinel\n" + PROMPT)
