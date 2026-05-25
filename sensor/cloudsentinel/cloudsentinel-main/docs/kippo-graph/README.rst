.. SPDX-FileCopyrightText: 2019-2024 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

How to send CloudSentinel output to kippo-graph
########################################

Kippo-Graph Prerequisites
=========================

* Working CloudSentinel installation
* LAMP stack (Linux, Apache, MySQL, PHP)

Kippo-Graph Installation
========================

This covers a simple installation, with kippo-graph and CloudSentinel on the same server.
Please see here for installation: https://github.com/ikoniaris/kippo-graph

MySQL configuration for Kippo-Graph
===================================

Configuring CloudSentinel requires setting up the SQL tables and then telling CloudSentinel to use them.

To install the tables and create the CloudSentinel user account enter the following commands::

    $ mysql -u root -p
    CREATE DATABASE cloudsentinel;
    GRANT ALL ON cloudsentinel.* TO 'cloudsentinel'@'localhost' IDENTIFIED BY 'PASSWORD HERE';
    FLUSH PRIVILEGES;
    exit

Next create the database schema::

    $ cd /opt/cloudsentinel/
    $ mysql -u cloudsentinel -p
    USE cloudsentinel;
    source ./docs/sql/mysql.sql;
    exit

disable MySQL strict mode::

    $ vi /etc/mysql/conf.d/disable_strict_mode.cnf

    [mysqld]
    sql_mode=IGNORE_SPACE,NO_ZERO_IN_DATE,NO_ZERO_DATE,ERROR_FOR_DIVISION_BY_ZERO,NO_AUTO_CREATE_USER,NO_ENGINE_SUBSTITUTION

CloudSentinel Configuration for Kippo-Graph
====================================

Edit cloudsentinel.cfg::

    $ vi etc/cloudsentinel.cfg

Activate output to mysql::

    [output_mysql]
    enabled = true
    host = localhost
    database = cloudsentinel
    username = cloudsentinel
    password = PASSWORD HERE
    port = 3306
    debug = false

Set read access to tty-files for group www-data (group maybe differ on other distributions)::

    $ sudo apt-get install acl
    $ sudo setfacl -Rm g:www-data:rx /opt/cloudsentinel/var/lib/cloudsentinel/tty/

Kippo-Graph Configuration
=========================

Edit config file::

    $ vi /var/www/html/kippo-graph/config.php

Change db settings::

    define('DB_HOST', 'localhost');
    define('DB_USER', 'cloudsentinel');
    define('DB_PASS', 'PASSWORD HERE');
    define('DB_NAME', 'cloudsentinel');
    define('DB_PORT', '3306');

Apache2 configuration (optional)
================================

To secure the installation

Create password database::

    $ cd /etc/apache2/
    $ htpasswd -c /etc/apache2/cloudsentinel.passwd <username>
    $ htpasswd /etc/apache2/cloudsentinel.passwd <username> (second user)


    $ vi /etc/apache2/sites-enabled/000-default.conf

Between the <VirtualHost> </VirtualHost> tags, add::

    <Location />
        AuthBasicAuthoritative On
        AllowOverride AuthConfig

        AuthType Basic
        AuthName "cloudsentinel honeypot"
        AuthUserFile /etc/apache2/cloudsentinel.passwd
        Require valid-user
    </Location>


