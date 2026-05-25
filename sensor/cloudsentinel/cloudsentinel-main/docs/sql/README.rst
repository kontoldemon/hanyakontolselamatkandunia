.. SPDX-FileCopyrightText: 2019-2025 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

How to Send CloudSentinel output to a MySQL or PostgreSQL Database
###########################################################

MySQL/PostgreSQL Output Plugin Prerequisites
============================================

* Working CloudSentinel installation
* Working MySQL installation
* Working PostgreSQL installation

MySQL Installation
==================

On your CloudSentinel server, run::

    $ su - cloudsentinel
    $ source cloudsentinel/cloudsentinel-env/bin/activate
    $ pip install mysql-connector-python

MySQL Configuration
===================

First create an empty database named ``cloudsentinel``::

    $ mysql -u root -p
    CREATE DATABASE cloudsentinel;

Create a CloudSentinel user account for the database and grant all access privileges::

    CREATE USER 'cloudsentinel'@'localhost' IDENTIFIED BY 'PASSWORD HERE';

**Restricted Privileges:**

Alternatively you can grant the CloudSentinel account fewer privileges. The following command grants the account with the
bare minimum required for the output logging to function::

    GRANT INSERT, SELECT, UPDATE ON cloudsentinel.* TO 'cloudsentinel'@'localhost';

Apply the privilege settings and exit mysql::

    FLUSH PRIVILEGES;
    exit

Next, log into the MySQL database using the CloudSentinel account to verify proper access privileges and load the database schema provided in the docs/sql/ directory::

    $ cd ~/cloudsentinel/docs/sql/
    $ mysql -u cloudsentinel -p
    USE cloudsentinel;
    source mysql.sql;
    exit

CloudSentinel Configuration for MySQL
==============================

Add the following entries to ``etc/cloudsentinel.cfg`` under the Output Plugins section::

    [output_mysql]
    host = localhost
    database = cloudsentinel
    username = cloudsentinel
    password = PASSWORD HERE
    port = 3306
    debug = false
    enabled = true

Restart CloudSentinel::

    $ cd ~/cloudsentinel/bin/
    $ ./cloudsentinel restart

Verify that the MySQL Output Engine Has Been Loaded

Check the end of the ``var/log/cloudsentinel/cloudsentinel.log`` to make
sure the MySQL output engine loaded successfully::

    $ cd ~/cloudsentinel/var/log/cloudsentinel/
    $ tail cloudsentinel.log

Example expected output::

    2017-11-27T22:19:44-0600 [-] Loaded output engine: jsonlog
    2017-11-27T22:19:44-0600 [-] Loaded output engine: mysql
    ...
    2017-11-27T22:19:58-0600 [-] Ready to accept SSH connections

## Confirm that events are logged to the MySQL Database

Wait for a new login attempt to occur. Use tail like before to quickly check if any activity has
been recorded in the cloudsentinel.log file.

Once a login event has occurred, log back into the MySQL database and verify that the event was recorded::

    $ mysql -u cloudsentinel -p
    USE cloudsentinel;
    SELECT * FROM auth;
    ``

Example output::

    +----+--------------+---------+----------+-------------+---------------------+
    | id | session      | success | username | password    | timestamp           |
    +----+--------------+---------+----------+-------------+---------------------+
    |  1 | a551c0a74e06 |       0 | root     | 12345       | 2017-11-27 23:15:56 |
    |  2 | a551c0a74e06 |       0 | root     | seiko2005   | 2017-11-27 23:15:58 |
    |  3 | a551c0a74e06 |       0 | root     | anko        | 2017-11-27 23:15:59 |
    |  4 | a551c0a74e06 |       0 | root     | 123456      | 2017-11-27 23:16:00 |
    |  5 | a551c0a74e06 |       0 | root     | dreambox    | 2017-11-27 23:16:01 |
    ...

PostgreSQL Installation
=======================

On your CloudSentinel server, run::

    $ su - cloudsentinel
    $ source cloudsentinel/cloudsentinel-env/bin/activate
    $ pip install psycopg2

PostgreSQL Configuration
========================

First create an empty database named ``cloudsentinel`` as a PostgreSQL superuser (e.g., ``postgres``)::

    $ psql -U postgres
    CREATE DATABASE cloudsentinel;

Create a CloudSentinel user account for the database and grant access privileges::

    CREATE USER cloudsentinel WITH PASSWORD 'PASSWORD HERE';
    GRANT CONNECT ON DATABASE cloudsentinel TO cloudsentinel;
    \c cloudsentinel
    GRANT USAGE ON SCHEMA public TO cloudsentinel;
    GRANT INSERT, SELECT, UPDATE ON ALL TABLES IN SCHEMA public TO cloudsentinel;
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT INSERT, SELECT, UPDATE ON TABLES TO cloudsentinel;
    \q

Log into the PostgreSQL database using the CloudSentinel account to verify proper access privileges and load the database schema provided in the ``docs/sql/`` directory::

    $ cd ~/cloudsentinel/docs/sql/
    $ psql -U cloudsentinel -d cloudsentinel -f postgres.sql

PostgreSQL Schema Update for Boolean Compatibility
==================================================

PostgreSQL does not support TINYINT. If you are porting the MySQL schema, update boolean-like fields to use PostgreSQL's ``BOOLEAN`` type or ``INTEGER`` with 0/1 semantics.

CloudSentinel Configuration for PostgreSQL
===================================

Add the following entries in ``etc/cloudsentinel.cfg`` under the Output Plugins section::

    [output_postgresql]
    enabled = true
    host = localhost
    database = cloudsentinel
    username = cloudsentinel
    password = PASSWORD HERE
    port = 5432
    debug = false

Restart CloudSentinel::

    $ cd ~/cloudsentinel/bin/
    $ ./cloudsentinel restart

Verify That the PostgreSQL Output Engine Has Been Loaded
========================================================

Check the end of the ``var/log/cloudsentinel/cloudsentinel.log`` to make sure that the PostgreSQL output engine has loaded successfully::

    $ cd ~/cloudsentinel/var/log/cloudsentinel/
    $ tail cloudsentinel.log

Example expected output::

    2025-04-07T22:20:00-0000 [-] Loaded output engine: jsonlog
    2025-04-07T22:20:00-0000 [-] Loaded output engine: postgresql
    ...
    2025-04-07T22:20:14-0000 [-] Ready to accept SSH connections

Confirm That Events are Logged to the PostgreSQL Database
==========================================================

Wait for a new login attempt to occur. Use ``tail`` like before to quickly check if any activity has been recorded in the ``cloudsentinel.log`` file.

Once a login event has occurred, log back into the PostgreSQL database and verify that the event was recorded::

    $ psql -U cloudsentinel -d cloudsentinel
    SELECT * FROM auth;

Example output::

     id |     session      | success | username | password  |     timestamp
    ----+------------------+---------+----------+-----------+---------------------
      1 | 863c26257d88     | t       | root     | 12345     | 2025-04-07 22:23:14
      2 | 863c26257d88     | f       | root     | dreambox  | 2025-04-07 22:23:15
    ...

