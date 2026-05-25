.. SPDX-FileCopyrightText: 2018 Carter Yagemann
.. SPDX-FileCopyrightText: 2018-2023 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

Using TCP tunneling with Squid
#################################

Squid Prerequisites
===================

* Working CloudSentinel installation
* Working Squid installation with CONNECT allowed
* Rate limit and black/white lists in Squid (optional)

Squid Installation
==================

Install Squid::

     $ sudo apt-get install squid

Squid Configuration
===================

See ``squid.conf`` for an example configuration.

CloudSentinel Configuration for Squid
==============================

Uncomment and update the following entries to ``etc/cloudsentinel.cfg`` under the SSH section::

    [ssh]
    forward_tunnel = true
    forward_tunnel_80 = 127.0.0.1:3128
    forward_tunnel_443 = 127.0.0.1:3128

## Restart CloudSentinel

Restart::

    $ bin/cloudsentinel restart
