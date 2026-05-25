.. SPDX-FileCopyrightText: 2019-2021 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

Automatically starting CloudSentinel with systemd
###########################################

NOTE: untested

* Copy the file ``docs/systemd/system/cloudsentinel.socket`` to ``/etc/systemd/system``

* Copy the file ``docs/systemd/system/cloudsentinel.service`` to ``/etc/systemd/system``

* Examine ``/etc/systemd/system/cloudsentinel.service`` and ensure the paths are correct for your installation if you use non-standard file system locations.

* Add entries to ``etc/cloudsentinel.cfg`` to listen on ports via systemd. These must match your cloudsentinel.socket configuration::

    [ssh]
    listen_endpoints = systemd:domain=INET6:index=0

    [telnet]
    listen_endpoints = systemd:domain=INET6:index=1

* Run::

    $ sudo systemctl daemon-reload
    $ sudo systemctl start cloudsentinel.service
    $ sudo systemctl enable cloudsentinel.service
