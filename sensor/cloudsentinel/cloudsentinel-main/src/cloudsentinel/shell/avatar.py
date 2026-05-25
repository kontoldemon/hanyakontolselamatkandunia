# SPDX-FileCopyrightText: 2009-2014 Upi Tamminen <desaster@gmail.com>
# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause


from __future__ import annotations

from twisted.conch import avatar
from twisted.conch.error import ConchError
from twisted.conch.interfaces import IConchUser, ISession, ISFTPServer
from twisted.conch.ssh import filetransfer as conchfiletransfer
from twisted.conch.ssh.connection import OPEN_UNKNOWN_CHANNEL_TYPE
from twisted.python import components, log
from zope.interface import implementer

from cloudsentinel.core.config import CloudSentinelConfig
from cloudsentinel.shell import filetransfer, pwd, server
from cloudsentinel.shell import session as shellsession
from cloudsentinel.ssh import forwarding
from cloudsentinel.ssh import session as sshsession


@implementer(IConchUser)
class CloudSentinelUser(avatar.ConchUser):
    def __init__(self, username: bytes, server: server.CloudSentinelServer) -> None:
        avatar.ConchUser.__init__(self)
        self.username: str = username.decode("utf-8")
        self.server = server

        self.channelLookup[b"session"] = sshsession.HoneyPotSSHSession

        self.temporary: bool
        try:
            pwentry = pwd.Passwd().getpwnam(self.username)
            self.temporary = False
        except KeyError:
            pwentry = pwd.Passwd().setpwentry(self.username)
            self.temporary = True

        self.uid = pwentry["pw_uid"]
        self.gid = pwentry["pw_gid"]
        self.home = pwentry["pw_dir"]

        # SFTP support enabled only when option is explicitly set
        if CloudSentinelConfig.getboolean("ssh", "sftp_enabled", fallback=False):
            self.subsystemLookup[b"sftp"] = conchfiletransfer.FileTransferServer

        # SSH forwarding disabled only when option is explicitly set
        if CloudSentinelConfig.getboolean("ssh", "forwarding", fallback=True):
            self.channelLookup[b"direct-tcpip"] = (
                forwarding.cloudsentinelOpenConnectForwardingClient
            )

    def logout(self) -> None:
        log.msg(f"avatar {self.username} logging out")

    def lookupChannel(self, channelType, windowSize, maxPacket, data):
        """
        Override this to get more info on the unknown channel
        """
        klass = self.channelLookup.get(channelType, None)
        if not klass:
            raise ConchError(
                OPEN_UNKNOWN_CHANNEL_TYPE, f"unknown channel: {channelType}"
            )
        else:
            return klass(
                remoteWindow=windowSize,
                remoteMaxPacket=maxPacket,
                data=data,
                avatar=self,
            )


components.registerAdapter(
    filetransfer.SFTPServerForCloudSentinelUser, CloudSentinelUser, ISFTPServer
)
components.registerAdapter(shellsession.SSHSessionForCloudSentinelUser, CloudSentinelUser, ISession)
