.. SPDX-FileCopyrightText: 2019-2025 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

Docker Repository
=================

Docker Images are available on Docker Hub: https://hub.docker.com/r/cloudsentinel/cloudsentinel

Docker Quick Start
******************

To run CloudSentinel in Docker::

    $ docker run -p 2222:2222 cloudsentinel/cloudsentinel
    $ ssh -p 2222 root@localhost


Configuring CloudSentinel in Docker with Environment Variables
*******************************************************

CloudSentinel in Docker can be configured using environment variables. The
variable starts with ``CLOUDSENTINEL_`` then has the section name in capitals,
followed by the stanza in capitals. This example enables
telnet support::

    CLOUDSENTINEL_TELNET_ENABLED=yes

And then start CloudSentinel as::

    $ docker run -e CLOUDSENTINEL_TELNET_ENABLED=yes -p 2223:2223 cloudsentinel/cloudsentinel
    $ telnet localhost 2223


Configuring CloudSentinel in Docker with Config Files
**********************************************

Alternatively, CloudSentinel in Docker can use an `etc` mount to store
configuration data. Docker can either mount a volume or a directory.

Mounting a volume or directory on `/etc` will make existing files
unavailable to CloudSentinel, so make sure to copy `userdb.txt` and
`cloudsentinel.cfg.dist` there too!

Create ```cloudsentinel.cfg``` inside the etc directory (or volume)
with the following contents to enable telnet in CloudSentinel in Docker::

    [telnet]
    enabled = yes

Start CloudSentinel as::

    $ docker run -p 2223:2223 --mount type=bind,source=./etc,target=/cloudsentinel/cloudsentinel-git/etc cloudsentinel/cloudsentinel
    $ telnet localhost 2223

Environment variables take precedence over the configuration file.


Building Docker Images
*******************************

If you want to make extensive changes to the Docker image, it may be easier to build
your own local docker image with::

    $ make docker-load
