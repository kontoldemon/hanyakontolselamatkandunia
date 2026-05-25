<!--
SPDX-FileCopyrightText: 2015-2019 Michel Oosterhof <michel@oosterhof.net>

SPDX-License-Identifier: BSD-3-Clause
-->

To create additional output plugins, place Python modules in this directory.

Plugins need to subclass cloudsentinel.core.output.Output and define at least the
methods 'start', 'stop' and 'write'

    import cloudsentinel.core.output

    class Output(cloudsentinel.core.output.Output):

        def start(self):

        def stop(self):

        def write( self, event ):


