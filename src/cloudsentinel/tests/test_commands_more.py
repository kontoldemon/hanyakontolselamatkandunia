"""Cover the remaining command fake-output branches."""

from __future__ import annotations

import time

from cloudsentinel.commands.base import commands
from cloudsentinel.vfs import VirtualFileSystem


class FakeProtocol:
    def __init__(self) -> None:
        self.username = "root"
        self.uid = 0
        self.gid = 0
        self.home = "/root"
        self.hostname = "unit-host"
        self.clientIP = "8.8.8.8"
        self.cwd = "/root"
        self.logintime = time.time()
        self.environ = {"HOME": "/root"}
        self.fs = VirtualFileSystem()
        self.fs.mkdir("/")
        self.fs.mkdir("/root")
        self.fs.mkfile("/root/file.txt", b"file\n")
        self.fs.mkdir("/etc")
        self.fs.mkfile("/etc/issue.net", b"USAS test\n")
        self.dispatched: list[bytes] = []
        self.out: list[str] = []
        self.err: list[str] = []

    def _dispatch_line(self, line: bytes) -> None:
        self.dispatched.append(line)

    def uptime(self) -> str:
        return "1 min"

    def write(self, data: str | bytes) -> None:
        self.out.append(data.decode() if isinstance(data, bytes) else data)

    def write_stdout(self, data: str | bytes) -> None:
        self.write(data)

    def write_stderr(self, data: str | bytes) -> None:
        self.err.append(data.decode() if isinstance(data, bytes) else data)


def _run(path: str, *args: str) -> FakeProtocol:
    protocol = FakeProtocol()
    commands[path](protocol, *args).call()
    return protocol


def test_command_output_branches() -> None:
    for path, args in [
        ("/usr/bin/who", ()),
        ("/usr/bin/w", ()),
        ("/bin/echo", ()),
        ("/bin/echo", ("-n", "hello")),
        ("/bin/echo", ("-n",)),
        ("/usr/bin/printf", ("a\\nb",)),
        ("/bin/cat", ("/missing",)),
        ("/bin/cat", ("/root",)),
        ("/bin/ls", ("-l",)),
        ("/bin/ls", ()),
        ("/usr/bin/wget", ()),
        ("/usr/bin/curl", ()),
        ("/bin/sh", ("-c", "id")),
        ("/bin/sh", ("-c",)),
        ("/usr/bin/python3", ("-c", "print(1)")),
        ("/usr/bin/python3", ("-c", "id")),
        ("/usr/bin/python3", ()),
        ("/usr/bin/perl", ("-e", "id")),
        ("/usr/bin/perl", ()),
        ("/usr/bin/php", ("-r", "x")),
        ("/usr/bin/php", ()),
        ("/usr/bin/last", ()),
        ("/etc/issue.net", ()),
        ("/usr/bin/sudo", ("id",)),
        ("/usr/bin/crontab", ("-l",)),
        ("/usr/bin/crontab", ()),
        ("/usr/bin/locate", ("x",)),
        ("/usr/bin/lsblk", ()),
        ("/usr/bin/dmesg", ()),
        ("/bin/cp", ()),
        ("/bin/cp", ("a", "b")),
        ("/bin/mv", ()),
        ("/bin/mv", ("a", "b")),
        ("/bin/rm", ()),
        ("/bin/rm", ("a",)),
        ("/bin/mkdir", ()),
        ("/bin/mkdir", ("a",)),
    ]:
        _run(path, *args)

    protocol = FakeProtocol()
    original = protocol.fs.listdir
    protocol.fs.listdir = lambda _path: (_ for _ in ()).throw(RuntimeError("ls failed"))  # type: ignore[method-assign]
    commands["/bin/ls"](protocol, "-l").call()
    assert protocol.err
    protocol.fs.listdir = original  # type: ignore[method-assign]
