# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2022-2026 IMA LLC

from .exportbomcsv import entry as exportbomcsv
from .exportmermaid import entry as exportmermaid

# Fusion will automatically call the start() and stop() functions.
commands = [
    exportbomcsv,
    exportmermaid,
]


# Assumes you defined a "start" function in each of your modules.
# The start function will be run when the add-in is started.
def start():
    for command in commands:
        command.start()


# Assumes you defined a "stop" function in each of your modules.
# The stop function will be run when the add-in is stopped.
def stop():
    for command in commands:
        command.stop()
