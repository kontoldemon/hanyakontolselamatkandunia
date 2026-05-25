.. SPDX-FileCopyrightText: 2022 udgover <frederic.baguelin@gmail.com>
.. SPDX-FileCopyrightText: 2023 Michel Oosterhof <michel@oosterhof.net>
..
.. SPDX-License-Identifier: BSD-3-Clause

How to send CloudSentinel output to Datadog Log Management
###################################################

This guide describes how to configure and send cloudsentinel outputs to Datadog Log Management.

Datadog output module Prerequisites
***********************************

* Working CloudSentinel installation
* Existing Datadog account.

CloudSentinel Configuration for Datadog output module
**********************************************

* Modify ``cloudsentinel.cfg`` to enable the ``[output_datadog]`` section.
* Add an API Key. You may generate one for your organisation from `here <https://app.datadoghq.com/organization-settings/api-keys>`_.
* Optionally customize ``ddsource``, ``ddtags`` and ``service``. Otherwise, defaults are respectively ``cloudsentinel``, ``env:prod`` and ``honeypot``.

Datadog Configuration
*********************

JSON logs are handled without further configuration in Datadog.
