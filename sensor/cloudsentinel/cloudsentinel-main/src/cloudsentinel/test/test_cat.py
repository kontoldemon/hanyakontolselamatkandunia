# SPDX-FileCopyrightText: 2020 Matej Dujava <mdujava@gmail.com>
# SPDX-FileCopyrightText: 2020-2024 Michel Oosterhof <michel@oosterhof.net>
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

PROMPT = b"root@unitTest:~# "


class ShellCatCommandTests(unittest.TestCase):
    """Test for cloudsentinel/commands/cat.py."""

    def setUp(self) -> None:
        self.proto = HoneyPotInteractiveProtocol(FakeAvatar(FakeServer()))
        self.tr = FakeTransport("", "31337")
        self.proto.makeConnection(self.tr)
        self.tr.clear()

    def tearDown(self) -> None:
        self.proto.connectionLost()

    def test_cat_command_001(self) -> None:
        self.proto.lineReceived(b"cat nonExisting\n")
        self.assertEqual(
            self.tr.value(), b"cat: nonExisting: No such file or directory\n" + PROMPT
        )

    def test_cat_command_002(self) -> None:
        self.proto.lineReceived(b"echo test | cat -\n")
        self.assertEqual(self.tr.value(), b"test\n" + PROMPT)

    def test_cat_command_003(self) -> None:
        self.proto.lineReceived(b"echo 1 | cat\n")
        self.proto.lineReceived(b"echo 2\n")
        self.proto.handle_CTRL_D()
        self.assertEqual(self.tr.value(), b"1\n" + PROMPT + b"2\n" + PROMPT)

    def test_cat_command_004(self) -> None:
        self.proto.lineReceived(b"cat\n")
        self.proto.lineReceived(b"test\n")
        self.proto.handle_CTRL_C()
        self.assertEqual(self.tr.value(), b"test\n^C\n" + PROMPT)
