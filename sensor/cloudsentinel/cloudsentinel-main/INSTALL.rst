.. SPDX-FileCopyrightText: 2019-2026 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

Installing CloudSentinel in seven steps
################################

This guide describes how to install CloudSentinel in ``shell`` mode with ``git clone``.
For ``proxy`` mode read `PROXY.rst`.

* :ref:`Step 1: Install system dependencies<INSTALL:Step 1: Install system dependencies>`
* :ref:`Step 2: Create a user account<INSTALL:Step 2: Create a user account>`
* :ref:`Step 3: Checkout the code<INSTALL:Step 3: Checkout the code>`
* :ref:`Step 4: Setup Virtual Environment<INSTALL:Step 4: Setup Virtual Environment>`
* :ref:`Step 5: Install configuration file<INSTALL:Step 5: Install configuration file>`
* :ref:`Step 6: Starting CloudSentinel<INSTALL:Step 6: Starting CloudSentinel>`
* :ref:`Step 7: Listening on port 22 (OPTIONAL)<INSTALL:Step 7: Listening on port 22 (OPTIONAL)>`
* :ref:`Installing Backend Pool dependencies (OPTIONAL)<INSTALL:Installing Backend Pool dependencies (OPTIONAL)>`
* :ref:`Running using supervisord (OPTIONAL)<INSTALL:Running using supervisord (OPTIONAL)>`
* :ref:`Configure Additional Output Plugins (OPTIONAL)<INSTALL:Configure Additional Output Plugins (OPTIONAL)>`
* :ref:`Troubleshooting<INSTALL:Troubleshooting>`
* :ref:`Updating CloudSentinel<INSTALL:Updating CloudSentinel>`
* :ref:`Modifying CloudSentinel<INSTALL:Modifying CloudSentinel>`

Step 1: Install system dependencies
***********************************

First we install system-wide support for Python virtual environments and other dependencies.
Actual Python packages are installed later.

On Debian based systems (last verified on Debian Bookworm)::

    $ sudo apt-get install git python3-pip python3-venv libssl-dev libffi-dev build-essential libpython3-dev python3-minimal authbind

Step 2: Create a user account
*****************************

It's strongly recommended to run with a dedicated non-root user id::

    $ sudo adduser --disabled-password cloudsentinel
    Adding user 'cloudsentinel' ...
    Adding new group 'cloudsentinel' (1002) ...
    Adding new user 'cloudsentinel' (1002) with group 'cloudsentinel' ...
    Changing the user information for cloudsentinel
    Enter the new value, or press ENTER for the default
    Full Name []:
    Room Number []:
    Work Phone []:
    Home Phone []:
    Other []:
    Is the information correct? [Y/n]

    $ sudo su - cloudsentinel

Step 3: Checkout the code
*************************

Check out the code::

    $ git clone http://github.com/cloudsentinel/cloudsentinel
    Cloning into 'cloudsentinel'...
    remote: Counting objects: 2965, done.
    remote: Compressing objects: 100% (1025/1025), done.
    remote: Total 2965 (delta 1908), reused 2962 (delta 1905), pack-reused 0
    Receiving objects: 100% (2965/2965), 3.41 MiB | 2.57 MiB/s, done.
    Resolving deltas: 100% (1908/1908), done.
    Checking connectivity... done.

    $ cd cloudsentinel

Step 4: Setup Virtual Environment
*********************************

Next you need to create your virtual environment::

    $ pwd
    /home/cloudsentinel/cloudsentinel
    $ python3 -m venv cloudsentinel-env
    New python executable in ./cloudsentinel/cloudsentinel-env/bin/python
    Installing setuptools, pip, wheel...done.

Activate the virtual environment and install packages::

    $ source cloudsentinel-env/bin/activate
    (cloudsentinel-env) $ python -m pip install --upgrade pip
    (cloudsentinel-env) $ python -m pip install -e .


Step 5: Install configuration file
**********************************

The configuration for CloudSentinel is stored in `cloudsentinel.cfg.dist` and
`cloudsentinel.cfg` (located in cloudsentinel/etc). Both files are read on startup, where entries from
`cloudsentinel.cfg` take precedence. The .dist file can be overwritten by
upgrades, `cloudsentinel.cfg` will not be touched. To run with a standard
configuration, there is no need to change anything. To enable telnet,
for example, create cloudsentinel.cfg and input only the following::

    [telnet]
    enabled = true

Step 6: Starting CloudSentinel
***********************

Start CloudSentinel with the `cloudsentinel` command. An existing virtual environment
is preserved if activated, otherwise CloudSentinel will attempt to load
the environment called "cloudsentinel-env"::


    $ source cloudsentinel-env/bin/activate
    (cloudsentinel-env) $ cloudsentinel start
    Starting cloudsentinel with extra arguments [] ...

Step 7: Listening on port 22 (OPTIONAL)
***************************************

The SSH daemon runs on port 22 by default. CloudSentinel runs on port 2222 by default.
To receive most traffic, CloudSentinel will need to listen on port 22. This requires two
changes: First, If you have an existing SSHD on port 22 it will need to be moved
to another port. Second, CloudSentinel will need to listen to requests on port 22.

There are three methods to make CloudSentinel accessible on the default SSH port (22): `iptables`, `authbind` and `setcap`.

Iptables
========

Port redirection commands are system-wide and need to be executed as root.
A firewall redirect can make your existing SSH server unreachable, remember to move the existing
server to a different port number first.

The following firewall rule will forward incoming traffic on port 22 to port 2222 on Linux::

    $ sudo iptables -t nat -A PREROUTING -p tcp --dport 22 -j REDIRECT --to-port 2222

With nft::

    $ sudo nft add rule ip nat prerouting tcp dport 22 redirect to 2222

Or for telnet::

    $ sudo iptables -t nat -A PREROUTING -p tcp --dport 23 -j REDIRECT --to-port 2223

Or with nft::

    $ sudo nft add rule ip nat prerouting tcp dport 23 redirect to 2223

Note that you should test this rule only from another host; it doesn't apply to loopback connections.

On MacOS run::

    $ echo "rdr pass inet proto tcp from any to any port 22 -> 127.0.0.1 port 2222" | sudo pfctl -ef -

Authbind
========

Alternatively you can run authbind to listen as non-root on port 22 directly::

    $ sudo apt-get install authbind
    $ sudo touch /etc/authbind/byport/22
    $ sudo chown cloudsentinel:cloudsentinel /etc/authbind/byport/22
    $ sudo chmod 770 /etc/authbind/byport/22

Change the listening port to 22 in cloudsentinel.cfg::

    [ssh]
    listen_endpoints = tcp:22:interface=0.0.0.0

Or for telnet::

    $ apt-get install authbind
    $ sudo touch /etc/authbind/byport/23
    $ sudo chown cloudsentinel:cloudsentinel /etc/authbind/byport/23
    $ sudo chmod 770 /etc/authbind/byport/23

Change the listening port to 23 in cloudsentinel.cfg::

    [telnet]
    listen_endpoints = tcp:23:interface=0.0.0.0

And start CloudSentinel with AUTHBIND_ENABLED::

    $ AUTHBIND_ENABLED=yes cloudsentinel start

Setcap
======

Or use setcap to give permissions to Python to listen on ports<1024::

    $ setcap cap_net_bind_service=+ep /usr/bin/python3

And change the listening ports in ``cloudsentinel.cfg`` as above.


Installing Backend Pool dependencies (OPTIONAL)
***********************************************

If you want to use the proxy functionality combined with the automatic
backend pool, you need to install some dependencies, namely QEMU, libvirt,
and their Python interface. In Debian/Ubuntu::

    $ sudo apt-get install qemu-system-arm qemu-system-x86 libvirt-dev libvirt-daemon libvirt-daemon-system libvirt-clients nmap

Then install the Python API to run the backend pool::


    $ source cloudsentinel-env/bin/activate
    (cloudsentinel-env) $ python -m pip install -e '.[pool]'

To allow QEMU to use disk images and snapshots, set it to run with the user and group of the user running the pool
(usually called 'cloudsentinel' too::

    $ sudo vi /etc/libvirt/qemu.conf

Search and set both `user` and `group` to `"cloudsentinel"`, or the username/group you'll be running the backend pool with.

Running using Supervisord (OPTIONAL)
************************************

On Debian, put the below in /etc/supervisor/conf.d/cloudsentinel.conf::

    [program:cloudsentinel]
    command=/home/cloudsentinel/cloudsentinel/bin/cloudsentinel start -n
    directory=/home/cloudsentinel/cloudsentinel/
    user=cloudsentinel
    autorestart=true
    redirect_stderr=true

Configure Additional Output Plugins (OPTIONAL)
**********************************************

CloudSentinel automatically outputs event data to text and JSON log files
in ``var/log/cloudsentinel``.  Additional output plugins can be configured to
record the data other ways.  Supported output plugins include:

* Cuckoo
* ELK (Elastic) Stack
* Graylog
* Splunk
* SQL (MySQL, SQLite3, RethinkDB)

See ~/cloudsentinel/docs/[Output Plugin]/README.rst for details.


Troubleshooting
***************

CryptographyDeprecationWarning: Blowfish has been deprecated
============================================================

The following warning may occur, this can be safely ignored, and
is not the reason your CloudSentinel installation is not working::

    CryptographyDeprecationWarning: TripleDES has been moved to cryptography.hazmat.decrepit.ciphers.algorithms.TripleDES and will be removed from cryptography.hazmat.primitives.ciphers.algorithms in 48.0.0.

twistd: unknown command: cloudsentinel
===============================

If you see ``twistd: Unknown command: cloudsentinel`` there are two
possibilities. If there's a Python stack trace, it probably means
there's a missing or broken dependency. If there's no stack trace,
double check that your PYTHONPATH is set to the source code directory.

Default file permissions
========================

To make CloudSentinel logfiles public readable, change the ``--umask 0077``
option in ``bin/cloudsentinel`` into ``--umask 0022``

General approach
================

Check the log file in ``var/log/cloudsentinel/cloudsentinel.log``.

Updating CloudSentinel
***************

First stop your honeypot. Then pull updates from GitHub, and upgrade your Python dependencies::

    (cloudsentinel-env) $ cloudsentinel stop
    (cloudsentinel-env) $ git pull
    (cloudsentinel-env) $ python -m pip install --upgrade -e .

If you use output plugins like SQL, Splunk, or ELK, remember to also upgrade your dependencies for these too::

    (cloudsentinel-env) $ python -m pip install --upgrade -r requirements-output.txt

And finally, restart CloudSentinel after finishing all updates::

    (cloudsentinel-env) $ cloudsentinel start

Modifying CloudSentinel
****************

The pre-login banner can be set by creating the file ``honeyfs/etc/issue.net``.
The post-login banner can be customized by editing ``honeyfs/etc/motd``.


Local testing with SSH
**********************

After starting CloudSentinel locally, you can test it by connecting via SSH.

1. Start CloudSentinel:

   cloudsentinel start

2. Connect using SSH (CloudSentinel listens on port 2222 by default):

   ssh -p 2222 root@localhost

3. If authentication fails, check etc/userdb.txt and ensure an allow rule exists.
   Rules are processed top-to-bottom and stop at the first match.

4. Logs are written to:

   var/log/cloudsentinel/cloudsentinel.log

   This file contains all recorded activity, including login attempts,
   successful authentications, and commands executed by connected sessions.
   It is useful for verifying that CloudSentinel is working and for observing
   attacker behavior during testing.
