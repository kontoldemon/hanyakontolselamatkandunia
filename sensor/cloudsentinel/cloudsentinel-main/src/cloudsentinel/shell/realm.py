# SPDX-FileCopyrightText: 2015-2026 Michel Oosterhof <michel@oosterhof.net>
#
# SPDX-License-Identifier: BSD-3-Clause

from __future__ import annotations

from twisted.conch.interfaces import IConchUser
from twisted.conch.telnet import ITelnetProtocol
from twisted.cred.portal import IRealm
from zope.interface import implementer

from cloudsentinel.shell import avatar as shellavatar
from cloudsentinel.shell import server as shellserver
from cloudsentinel.telnet import session


@implementer(IRealm)
class HoneyPotRealm:
    def __init__(self) -> None:
        pass

    def requestAvatar(self, avatarId, _mind, *interfaces):
        user: IConchUser
        if IConchUser in interfaces:
            serv = shellserver.CloudSentinelServer(self)
            user = shellavatar.CloudSentinelUser(avatarId, serv)
            return interfaces[0], user, user.logout
        if ITelnetProtocol in interfaces:
            serv = shellserver.CloudSentinelServer(self)
            user = session.HoneyPotTelnetSession(avatarId, serv)
            return interfaces[0], user, user.logout
        raise NotImplementedError
