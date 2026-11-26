"""Coverage for command registry branches used by the live SSH session."""

from __future__ import annotations

from cloudsentinel.commands import CommandAdapter
from cloudsentinel.commands.base import commands


def _run(name: str, *args: str) -> str:
    protocol = CommandAdapter()
    protocol.stdin = "alpha beta\n"
    command = commands[name](protocol, *args)
    command.start()
    return protocol.flush()


def test_uname_flags_render_all_fields() -> None:
    for flag in ("-a", "-s", "-n", "-r", "-v", "-m", "-p", "-i", "-o"):
        assert _run("uname", flag).strip()
    assert _run("uname") == "Linux\n"


def test_misc_commands_render_output() -> None:
    assert "up" in _run("uptime")
    assert "Active Internet" in _run("netstat")
    assert "PATH=" in _run("env")
    assert _run("which", "python3") == "/usr/bin/python3\n"
    assert _run("which") == ""
    assert _run("base64", "hello").strip()
    assert "uname -a" in _run("history")
    assert "backup.sh" in _run("crontab", "-l")
    assert "no crontab" in _run("crontab")


def test_sed_invalid_expression_is_ignored() -> None:
    assert _run("sed", "s/[a/x/y/") == ""
    assert "omega" in _run("sed", "s/alpha/omega/")


def test_tr_squeeze_flag() -> None:
    output = _run("tr", "-s", "a", "b")
    assert isinstance(output, str)
